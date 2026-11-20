import com.sun.jdi.*;
import com.sun.jdi.connect.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Real JDI observations. No evaluation or user toString calls. */
public class SpandyTracer {
    static VirtualMachine vm;
    static Process process;
    static List<Object> steps = new ArrayList<>();
    static Map<String,Object> objects;
    static List<String> signatures=new ArrayList<>(), frameIds=new ArrayList<>();
    static int nextFrame=0;
    static String reason="completed", status="completed";
    static ByteCapture out,err;
    static Path workspace;
    static boolean interactive;
    static String traceBase;
    static String sourceFile=System.getProperty("spandy.source","Main.java"), entryClass=System.getProperty("spandy.entry","Main");
    static int maxSteps, publishedCount;
    static long publishedAt;
    static Set<ReferenceType> userClasses=new LinkedHashSet<>();
    static Map<String,Object> map(Object... pairs) {
        Map<String,Object> m=new LinkedHashMap<>();
        for(int i=0;i<pairs.length;i+=2) m.put((String)pairs[i],pairs[i+1]);
        return m;
    }
    static class ByteCapture extends Thread {
        InputStream stream; OutputStream file; ByteArrayOutputStream buffer=new ByteArrayOutputStream(); volatile boolean limited=false;
        ByteCapture(InputStream s,Path p)throws IOException{ stream=s;file=Files.newOutputStream(p);setDaemon(true);start(); }
        synchronized void drain()throws IOException{byte[] chunk=new byte[1024];while(stream.available()>0){int n=stream.read(chunk,0,Math.min(chunk.length,stream.available()));if(n<0)break;int left=8192-buffer.size(),count=Math.min(left,n);buffer.write(chunk,0,count);file.write(chunk,0,count);if(n>left){limited=true;break;}}file.flush();}
        public void run(){try{while(process.isAlive()&&!limited){drain();Thread.sleep(3);}drain();}catch(IOException|InterruptedException e){} }
        synchronized String text(){try{drain();}catch(IOException e){}return buffer.toString(StandardCharsets.UTF_8).replace("\r\n","\n");}
        synchronized void close()throws IOException{drain();file.close();}
    }
    static void publish(boolean force)throws IOException {
        if(!interactive)return;
        long now=System.nanoTime();
        if(!force&&publishedCount>0&&steps.size()-publishedCount<64&&now-publishedAt<200_000_000L)return;
        Path temporary=workspace.resolve("partial.json.tmp");
        Files.writeString(temporary,traceBase.substring(0,traceBase.length()-1)+",\"steps\":"+json(steps)+"}",StandardCharsets.UTF_8);
        replace(temporary,workspace.resolve("partial.json"));
        temporary=workspace.resolve("progress.json.tmp");Files.writeString(temporary,"{\"steps\":"+steps.size()+"}");
        replace(temporary,workspace.resolve("progress.json"));
        publishedCount=steps.size();publishedAt=now;
    }
    static void replace(Path temporary,Path target)throws IOException {
        for(int attempt=0;;attempt++)try{Files.move(temporary,target,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);return;}
        catch(AccessDeniedException e){if(attempt>=49)throw e;try{Thread.sleep(5);}catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new IOException(interrupted);}}
    }
    static Map<String,Object> val(Value v,int depth) {
        if(v==null)return map("kind","null","type","null","value",null);
        String type=v.type().name();
        if(v instanceof PrimitiveValue) {
            Object value;
            if(v instanceof BooleanValue)value=((BooleanValue)v).value();
            else if(v instanceof CharValue)value=String.valueOf(((CharValue)v).value());
            else if(v instanceof FloatValue || v instanceof DoubleValue){double d=((PrimitiveValue)v).doubleValue();value=Double.isFinite(d)?d:String.valueOf(d);}
            else {long n=((PrimitiveValue)v).longValue();value=n>9007199254740991L||n< -9007199254740991L?Long.toString(n):n;}
            return map("kind","primitive","type",type,"value",value);
        }
        if(v instanceof StringReference){String s=((StringReference)v).value();return map("kind","primitive","type","String","value",s.substring(0,Math.min(s.length(),300)),"truncated",s.length()>300);}
        if(v instanceof VoidValue)return map("kind","unavailable","type","void");
        if(!(v instanceof ObjectReference))return map("kind","unavailable","type",type);
        ObjectReference ref=(ObjectReference)v;
        if(!userClasses.contains(ref.referenceType())&&!(ref instanceof ArrayReference))return map("kind","unavailable","type",type,"note","Standard-library object internals are not inspected.");
        String id="j"+ref.uniqueID();
        if(!objects.containsKey(id)) {
            if(objects.size()>=80)return map("kind","unavailable","type",type,"truncated",true,"note","Object limit reached.");
            Map<String,Object> record=map("id",id,"type",type,"kind",ref instanceof ArrayReference?"sequence":"instance","items",new ArrayList<>(),"fields",new LinkedHashMap<>(),"entries",new ArrayList<>(),"truncated",false);
            objects.put(id,record);
            if(depth>=6){record.put("truncated",true);record.put("note","Maximum traversal depth reached.");}
            else if(ref instanceof ArrayReference){ArrayReference a=(ArrayReference)ref;List<Object> items=new ArrayList<>();int len=a.length();for(Value x:a.getValues(0,Math.min(len,40)))items.add(val(x,depth+1));record.put("items",items);record.put("length",len);record.put("truncated",len>40);}
            else {Map<String,Object> fields=new LinkedHashMap<>();int count=0;for(Field f:ref.referenceType().allFields()){if(f.isStatic()||f.isSynthetic())continue;if(count++>=40){record.put("truncated",true);break;}try{fields.put(f.name(),val(ref.getValue(f),depth+1));}catch(RuntimeException e){fields.put(f.name(),map("kind","unavailable","type",f.typeName()));}}record.put("fields",fields);}
        }
        return map("kind","reference","type",type,"ref",id);
    }
    static boolean user(Location loc) {
        try{return loc.sourceName().equals(sourceFile) && loc.lineNumber()>0;}catch(AbsentInformationException e){return false;}
    }
    static void snapshot(ThreadReference thread,Location location,String event,Value returned,Object exception) throws Exception {
        if(steps.size()>=maxSteps-1){reason="step_limit";status="truncated";return;}
        if(out.limited||err.limited){reason="output_limit";status="truncated";return;}
        objects=new LinkedHashMap<>();
        List<Object> frames=new ArrayList<>();
        List<StackFrame> observed=new ArrayList<>(thread.frames());Collections.reverse(observed);
        List<String> nextSig=new ArrayList<>();
        for(StackFrame frame:observed){if(!user(frame.location()))continue;Method method=frame.location().method();nextSig.add(method.declaringType().name()+"."+method.name()+method.signature());}
        if(nextSig.size()>50){status="truncated";reason="step_limit";return;}
        int common=0;while(common<nextSig.size()&&common<signatures.size()&&nextSig.get(common).equals(signatures.get(common)))common++;
        frameIds=new ArrayList<>(frameIds.subList(0,common));for(int i=common;i<nextSig.size();i++)frameIds.add("f"+(++nextFrame));signatures=nextSig;
        int index=0;
        for(StackFrame frame:observed){if(!user(frame.location()))continue;
            Map<String,Object> locals=new LinkedHashMap<>();
            if(frame.thisObject()!=null)locals.put("this",val(frame.thisObject(),0));
            try{List<LocalVariable> visible=frame.visibleVariables();Map<LocalVariable,Value> values=frame.getValues(visible.subList(0,Math.min(100,visible.size())));for(LocalVariable local:visible){if(locals.size()>=100)break;locals.put(local.name(),val(values.get(local),0));}}catch(AbsentInformationException e){locals.put("<locals>",map("kind","unavailable","type","unknown","note","No debug information is available."));}
            frames.add(map("id",frameIds.get(index++),"name",frame.location().method().name(),"line",frame.location().lineNumber(),"locals",locals));
        }
        Map<String,Object> globals=new LinkedHashMap<>();
        for(ReferenceType cls:userClasses){List<Field> fields=new ArrayList<>();for(Field f:cls.allFields())if(f.isStatic()&&!f.isSynthetic())fields.add(f);try{Map<Field,Value> values=cls.getValues(fields);for(Field f:fields)if(globals.size()<100)globals.put(cls.name()+"."+f.name(),val(values.get(f),0));}catch(RuntimeException e){} }
        Map<String,Object> ret=returned==null?null:val(returned,0);
        steps.add(map("index",steps.size(),"event",event,"location",map("file",sourceFile,"line",location.lineNumber(),"phase",event.equals("return")?"after":"before"),"frames",frames,"globals",globals,"objects",objects,"stdout",out.text(),"stderr",err.text(),"exception",exception,"returnValue",ret));
        publish(false);
        if(event.equals("return")&&!frameIds.isEmpty()){frameIds.remove(frameIds.size()-1);signatures.remove(signatures.size()-1);}
    }
    static void step(ThreadReference thread) {
        EventRequestManager manager=vm.eventRequestManager();
        for(StepRequest old:new ArrayList<>(manager.stepRequests()))manager.deleteEventRequest(old);
        StepRequest req=manager.createStepRequest(thread,StepRequest.STEP_LINE,StepRequest.STEP_INTO);
        for(String pattern:List.of("java.*","javax.*","jdk.*","sun.*","com.sun.*","SpandyRun*"))req.addClassExclusionFilter(pattern);
        req.addCountFilter(1);req.setSuspendPolicy(EventRequest.SUSPEND_ALL);req.enable();
    }
    static String json(Object obj) {
        if(obj==null)return "null";
        if(obj instanceof String){String s=(String)obj;StringBuilder b=new StringBuilder("\"");for(char c:s.toCharArray())switch(c){case '"':b.append("\\\"");break;case '\\':b.append("\\\\");break;case '\n':b.append("\\n");break;case '\r':b.append("\\r");break;case '\t':b.append("\\t");break;default:if(c<32)b.append(String.format("\\u%04x",(int)c));else b.append(c);}return b.append('"').toString();}
        if(obj instanceof Map){List<String> pairs=new ArrayList<>();for(var e:((Map<?,?>)obj).entrySet())pairs.add(json(e.getKey())+":"+json(e.getValue()));return "{"+String.join(",",pairs)+"}";}
        if(obj instanceof Iterable){List<String> items=new ArrayList<>();for(Object x:(Iterable<?>)obj)items.add(json(x));return "["+String.join(",",items)+"]";}
        return obj.toString(); // Only debugger-owned primitives and maps reach this serializer.
    }
    public static void main(String[] args) throws Exception {
        workspace=Path.of(args[0]);interactive=Files.exists(workspace.resolve("interactive.flag"));traceBase=Files.readString(workspace.resolve("trace-base.json")).trim();
        maxSteps=Integer.parseInt(Files.readString(workspace.resolve("visualize.flag")).trim());
        LaunchingConnector connector=Bootstrap.virtualMachineManager().defaultConnector();
        Map<String,Connector.Argument> params=connector.defaultArguments();
        params.get("main").setValue(interactive?"SpandyRun":entryClass);params.get("options").setValue("-Xmx"+System.getProperty("spandy.heapMiB","192")+"m -Dfile.encoding=UTF-8 -Dspandy.source="+sourceFile+" -Dspandy.entry="+entryClass+" -Dspandy.workspace=\""+workspace.toAbsolutePath()+"\" -XX:+UseSerialGC -XX:CICompilerCount=2 -cp \""+workspace.toAbsolutePath()+"\"");params.get("suspend").setValue("true");
        vm=connector.launch(params);process=vm.process();out=new ByteCapture(process.getInputStream(),workspace.resolve("stdout.txt"));err=new ByteCapture(process.getErrorStream(),workspace.resolve("stderr.txt"));
        byte[] input=Files.readAllBytes(workspace.resolve("stdin.txt"));process.getOutputStream().write(input);process.getOutputStream().close();
        EventRequestManager manager=vm.eventRequestManager();
        ClassPrepareRequest prepare=manager.createClassPrepareRequest();
        if(vm.canUseSourceNameFilters())prepare.addSourceNameFilter(sourceFile);
        prepare.setSuspendPolicy(EventRequest.SUSPEND_ALL);prepare.enable();
        ExceptionRequest exceptions=manager.createExceptionRequest(null,true,true);exceptions.setSuspendPolicy(EventRequest.SUSPEND_ALL);exceptions.enable();
        boolean done=false;
        try {while(!done&&reason.equals("completed")){
            if(Files.exists(workspace.resolve("checkpoint-request"))){publish(true);Files.delete(workspace.resolve("checkpoint-request"));}
            EventSet events=vm.eventQueue().remove(50);if(events==null)continue;
            for(Event event:events){
                if(event instanceof VMDeathEvent||event instanceof VMDisconnectEvent){done=true;break;}
                if(event instanceof ClassPrepareEvent){ReferenceType cls=((ClassPrepareEvent)event).referenceType();boolean own=false;try{own=cls.sourceNames(null).contains(sourceFile);}catch(AbsentInformationException ignored){}
                    if(own&&userClasses.add(cls)){MethodEntryRequest entry=manager.createMethodEntryRequest();entry.addClassFilter(cls);entry.setSuspendPolicy(EventRequest.SUSPEND_ALL);entry.enable();MethodExitRequest exit=manager.createMethodExitRequest();exit.addClassFilter(cls);exit.setSuspendPolicy(EventRequest.SUSPEND_ALL);exit.enable();}}
                if(event instanceof MethodEntryEvent){var e=(MethodEntryEvent)event;if(user(e.location())){snapshot(e.thread(),e.location(),"call",null,null);step(e.thread());}}
                else if(event instanceof StepEvent){var e=(StepEvent)event;if(user(e.location()))snapshot(e.thread(),e.location(),"line",null,null);step(e.thread());}
                else if(event instanceof MethodExitEvent){var e=(MethodExitEvent)event;if(user(e.location()))snapshot(e.thread(),e.location(),"return",vm.canGetMethodReturnValues()?e.returnValue():null,null);}
                else if(event instanceof ExceptionEvent){var e=(ExceptionEvent)event;if(user(e.location())){ObjectReference ex=e.exception();String message="";Field detail=ex.referenceType().fieldByName("detailMessage");if(detail!=null&&ex.getValue(detail) instanceof StringReference)message=((StringReference)ex.getValue(detail)).value();snapshot(e.thread(),e.location(),"exception",null,map("type",ex.referenceType().name(),"message",message.substring(0,Math.min(4096,message.length()))));if(e.catchLocation()==null){status="failed";reason="runtime_error";}}}
            }
            if(!done)events.resume();
        }}catch(VMDisconnectedException e){done=true;}finally{if(!done)try{vm.exit(1);}catch(RuntimeException e){}process.waitFor();out.join(300);err.join(300);}
        if(out.limited||err.limited){status="truncated";reason="output_limit";}
        if(status.equals("completed")&&process.exitValue()!=0){status="failed";reason="runtime_error";}
        Map<String,Object> last=steps.isEmpty()?map("globals",new LinkedHashMap<>(),"objects",new LinkedHashMap<>()):(Map<String,Object>)steps.get(steps.size()-1);
        steps.add(map("index",steps.size(),"event",status.equals("completed")?"completed":"terminated","location",null,"frames",new ArrayList<>(),"globals",last.get("globals"),"objects",last.get("objects"),"stdout",out.text(),"stderr",err.text(),"exception",null,"note",reason));
        out.close();err.close();
        Files.writeString(workspace.resolve("jdi.json"),json(map("runtimeVersion",System.getProperty("java.version"),"status",status,"terminationReason",reason,"steps",steps)),StandardCharsets.UTF_8);
    }
}
