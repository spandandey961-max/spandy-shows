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
    record RecordedFrame(Method method,String id) {}
    static Map<Long,Map<Integer,RecordedFrame>> stacks=new HashMap<>();
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
        synchronized void drain()throws IOException{
            byte[] chunk=new byte[4096];
            for(int available=stream.available();available>0;){
                int n=stream.read(chunk,0,Math.min(chunk.length,available));if(n<=0)break;
                int count=Math.min(65536-buffer.size(),n);
                buffer.write(chunk,0,count);file.write(chunk,0,count);
                if(n>count)limited=true;
                available-=n;
            }
            file.flush();
        }
        public void run(){try{while(process.isAlive()){drain();Thread.sleep(3);}drain();}catch(IOException|InterruptedException e){} }
        synchronized String text(int limit){try{drain();}catch(IOException e){}String value=buffer.toString(StandardCharsets.UTF_8);return value.substring(0,Math.min(limit,value.length())).replace("\r\n","\n");}
        synchronized void close()throws IOException{drain();file.close();}
    }
    static void publish(boolean force)throws IOException {
        if(!interactive)return;
        long now=System.nanoTime();
        if(!force&&publishedCount>0&&(steps.size()-publishedCount<Math.max(64,publishedCount/4)||now-publishedAt<1_000_000_000L))return;
        Path temporary=workspace.resolve("partial.json.tmp");
        Files.writeString(temporary,traceBase.substring(0,traceBase.length()-1)+",\"steps\":"+json(steps)+"}",StandardCharsets.UTF_8);
        replace(temporary,workspace.resolve("partial.json"));
        temporary=workspace.resolve("progress.json.tmp");Files.writeString(temporary,"{\"steps\":"+steps.size()+"}");
        replace(temporary,workspace.resolve("progress.json"));
        publishedCount=steps.size();publishedAt=now;
    }
    static void replace(Path temporary,Path target)throws IOException {
        for(int attempt=0;;attempt++)try{Files.move(temporary,target,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE);return;}
        catch(FileSystemException e){if(attempt>=49)throw e;try{Thread.sleep(5);}catch(InterruptedException interrupted){Thread.currentThread().interrupt();throw new IOException(interrupted);}}
    }
    static Value field(ObjectReference ref,String name){
        Field field=ref.referenceType().fieldByName(name);
        return field==null?null:ref.getValue(field);
    }
    static final Set<String> BOXES=Set.of("java.lang.Integer","java.lang.Long","java.lang.Short","java.lang.Byte",
        "java.lang.Boolean","java.lang.Character","java.lang.Double","java.lang.Float");
    static final Map<String,String> ARRAYS=Map.of(
        "java.util.ArrayList","elementData","java.util.Vector","elementData","java.util.Stack","elementData",
        "java.util.PriorityQueue","queue","java.util.ArrayDeque","elements",
        "java.util.Arrays$ArrayList","a","java.util.ImmutableCollections$ListN","elements");
    static final Set<String> MAPS=Set.of("java.util.HashMap","java.util.LinkedHashMap","java.util.HashSet","java.util.LinkedHashSet");
    static final Set<String> TREES=Set.of("java.util.TreeMap","java.util.TreeSet");
    static final String IMMUTABLE="java.util.ImmutableCollections$";
    static final String CONCURRENT_MAP="java.util.concurrent.ConcurrentHashMap";
    static final Set<String> FACTORY_COLLECTIONS=Set.of(IMMUTABLE+"List12",IMMUTABLE+"Set12",
        IMMUTABLE+"SetN",IMMUTABLE+"Map1",IMMUTABLE+"MapN");

    static java.math.BigInteger integer(ObjectReference ref){
        if(!(field(ref,"mag") instanceof ArrayReference mag)||mag.length()>128)return null;
        java.nio.ByteBuffer bytes=java.nio.ByteBuffer.allocate(mag.length()*4);
        for(Value word:mag.getValues())bytes.putInt(((IntegerValue)word).value());
        return new java.math.BigInteger(((IntegerValue)field(ref,"signum")).value(),bytes.array());
    }
    static Map<String,Object> scalar(ObjectReference ref,String type){
        try{
            if(type.equals("java.math.BigInteger")){
                var value=integer(ref);
                if(value!=null)return map("kind","primitive","type",type,"value",value.toString());
            }else if(type.equals("java.math.BigDecimal")){
                long compact=((LongValue)field(ref,"intCompact")).value();
                int scale=((IntegerValue)field(ref,"scale")).value();
                var unscaled=compact!=Long.MIN_VALUE?java.math.BigInteger.valueOf(compact):integer((ObjectReference)field(ref,"intVal"));
                if(unscaled!=null)return map("kind","primitive","type",type,"value",new java.math.BigDecimal(unscaled,scale).toString());
            }else if(type.equals("java.lang.StringBuilder")||type.equals("java.lang.StringBuffer")){
                ArrayReference storage=(ArrayReference)field(ref,"value");
                int width=((ByteValue)field(ref,"coder")).value()+1;
                int total=((IntegerValue)field(ref,"count")).value();
                List<Value> bytes=storage.getValues(0,Math.min(total,300)*width);
                StringBuilder text=new StringBuilder();
                boolean little=java.nio.ByteOrder.nativeOrder()==java.nio.ByteOrder.LITTLE_ENDIAN;
                for(int i=0;i<bytes.size();i+=width){
                    int a=((ByteValue)bytes.get(i)).value()&255;
                    if(width==1)text.append((char)a);
                    else {int b=((ByteValue)bytes.get(i+1)).value()&255;text.append((char)(little?a|(b<<8):(a<<8)|b));}
                }
                return map("kind","primitive","type",type,"value",text.toString(),"truncated",total>300);
            }
        }catch(RuntimeException ignored) {}
        return null;
    }

    static void inspectCollection(ObjectReference ref,Map<String,Object> record,int depth){
        String type=ref.referenceType().name();
        List<Object> items=new ArrayList<>();
        List<Object> entries=new ArrayList<>();
        int length;
        if(ref instanceof ArrayReference array){
            length=array.length();
            for(Value item:array.getValues(0,Math.min(length,40)))items.add(val(item,depth+1));
        }else if(type.equals(IMMUTABLE+"List12")||type.equals(IMMUTABLE+"Set12")){
            Value second=field(ref,"e1");
            Value empty=ref.virtualMachine().classesByName("java.util.ImmutableCollections").stream()
                .findFirst().map(owner->owner.getValue(owner.fieldByName("EMPTY"))).orElse(null);
            items.add(val(field(ref,"e0"),depth+1));
            if(!Objects.equals(second,empty))items.add(val(second,depth+1));
            length=items.size();
            if(type.endsWith("Set12"))record.put("kind","set");
        }else if(type.equals(IMMUTABLE+"SetN")||type.equals(IMMUTABLE+"MapN")){
            boolean set=type.endsWith("SetN");
            length=((IntegerValue)field(ref,"size")).value();
            ArrayReference storage=(ArrayReference)field(ref,set?"elements":"table");
            int stride=set?1:2;
            List<Value> slots=storage.getValues(0,Math.min(storage.length(),2048));
            for(int i=0;i<slots.size()&&items.size()+entries.size()<Math.min(length,40);i+=stride){
                if(slots.get(i)==null)continue;
                Object key=val(slots.get(i),depth+1);
                if(set)items.add(key);else entries.add(List.of(key,val(slots.get(i+1),depth+1)));
            }
            record.put("kind",set?"set":"mapping");
        }else if(type.equals(IMMUTABLE+"Map1")){
            length=1;
            entries.add(List.of(val(field(ref,"k0"),depth+1),val(field(ref,"v0"),depth+1)));
            record.put("kind","mapping");
        }else if(type.equals(CONCURRENT_MAP)){
            long count=((LongValue)field(ref,"baseCount")).value();
            if(field(ref,"counterCells") instanceof ArrayReference counters){
                for(Value value:counters.getValues())if(value instanceof ObjectReference cell)
                    count+=((LongValue)field(cell,"value")).value();
            }
            length=(int)Math.max(0,Math.min(count,Integer.MAX_VALUE));
            if(field(ref,"table") instanceof ArrayReference table){
                for(Value bucket:table.getValues(0,Math.min(table.length(),2048))){
                    Value node=bucket;
                    if(node instanceof ObjectReference link&&link.referenceType().name().endsWith("$TreeBin"))
                        node=field(link,"first");
                    while(node instanceof ObjectReference link&&entries.size()<40){
                        Value key=field(link,"key");
                        if(key!=null)entries.add(List.of(val(key,depth+1),val(field(link,"val"),depth+1)));
                        node=field(link,"next");
                    }
                    if(entries.size()==40)break;
                }
            }
            record.put("kind","mapping");
            length=Math.max(length,entries.size());
        }else if(type.equals("java.util.LinkedList")){
            length=((IntegerValue)field(ref,"size")).value();
            Value node=field(ref,"first");
            while(node instanceof ObjectReference link&&items.size()<Math.min(length,40)){
                items.add(val(field(link,"item"),depth+1));node=field(link,"next");
            }
        }else if(TREES.contains(type)){
            boolean set=type.endsWith("Set");
            ObjectReference tree=set?(ObjectReference)field(ref,"m"):ref;
            length=((IntegerValue)field(tree,"size")).value();
            Deque<ObjectReference> stack=new ArrayDeque<>();
            Value node=field(tree,"root");
            while((node!=null||!stack.isEmpty())&&items.size()+entries.size()<Math.min(length,40)){
                while(node instanceof ObjectReference branch&&stack.size()<128){
                    stack.push(branch);node=field(branch,"left");
                }
                if(stack.isEmpty()||node!=null)break;
                ObjectReference branch=stack.pop();
                Object key=val(field(branch,"key"),depth+1);
                if(set)items.add(key);else entries.add(List.of(key,val(field(branch,"value"),depth+1)));
                node=field(branch,"right");
            }
            record.put("kind",set?"set":"mapping");
        }else if(MAPS.contains(type)){
            boolean set=type.endsWith("Set");
            ObjectReference hash=set?(ObjectReference)field(ref,"map"):ref;
            length=((IntegerValue)field(hash,"size")).value();
            if(hash.referenceType().name().equals("java.util.LinkedHashMap")){
                Value node=field(hash,"head");
                while(node instanceof ObjectReference link&&items.size()+entries.size()<Math.min(length,40)){
                    Object key=val(field(link,"key"),depth+1);
                    if(set)items.add(key);else entries.add(List.of(key,val(field(link,"value"),depth+1)));
                    node=field(link,"after");
                }
            }else if(field(hash,"table") instanceof ArrayReference table){
                int reserved=Math.min(table.length(),2048);
                for(Value bucket:table.getValues(0,reserved)){
                    Value node=bucket;
                    while(node instanceof ObjectReference link&&items.size()+entries.size()<Math.min(length,40)){
                        Object key=val(field(link,"key"),depth+1);
                        if(set)items.add(key);
                        else entries.add(List.of(key,val(field(link,"value"),depth+1)));
                        node=field(link,"next");
                    }
                    if(items.size()+entries.size()>=Math.min(length,40))break;
                }
            }
            record.put("kind",set?"set":"mapping");
        }else{
            ArrayReference array=(ArrayReference)field(ref,ARRAYS.get(type));
            int start=0;
            if(type.equals("java.util.ArrayDeque")){
                start=((IntegerValue)field(ref,"head")).value();
                int tail=((IntegerValue)field(ref,"tail")).value();
                length=Math.floorMod(tail-start,array.length());
            }else if(type.equals("java.util.Arrays$ArrayList")||type.equals(IMMUTABLE+"ListN")){
                length=array.length();
            }else{
                String size=type.equals("java.util.Vector")||type.equals("java.util.Stack")?"elementCount":"size";
                length=((IntegerValue)field(ref,size)).value();
            }
            for(int i=0;i<Math.min(length,40);i++)items.add(val(array.getValue((start+i)%array.length()),depth+1));
            if(type.equals("java.util.PriorityQueue"))record.put("note","Internal heap order. Polling the queue returns elements in priority order.");
        }
        record.put("items",items);record.put("entries",entries);record.put("length",length);
        record.put("truncated",items.size()+entries.size()<length);
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
        if(BOXES.contains(type)&&field(ref,"value") instanceof PrimitiveValue primitive){
            Map<String,Object> value=val(primitive,depth);value.put("type",type);return value;
        }
        Map<String,Object> scalar=scalar(ref,type);
        if(scalar!=null)return scalar;
        boolean collection=ref instanceof ArrayReference||ARRAYS.containsKey(type)||MAPS.contains(type)||TREES.contains(type)
            ||FACTORY_COLLECTIONS.contains(type)||type.equals(CONCURRENT_MAP)||type.equals("java.util.LinkedList");
        if(!userClasses.contains(ref.referenceType())&&!collection)return map("kind","unavailable","type",type,"note","This library type has no memory inspector.");
        String id="j"+ref.uniqueID();
        if(!objects.containsKey(id)) {
            if(objects.size()>=80)return map("kind","unavailable","type",type,"truncated",true,"note","Object limit reached.");
            Map<String,Object> record=map("id",id,"type",type,"kind",collection?"sequence":"instance","items",new ArrayList<>(),"fields",new LinkedHashMap<>(),"entries",new ArrayList<>(),"truncated",false);
            objects.put(id,record);
            if(depth>=6){record.put("truncated",true);record.put("note","Maximum traversal depth reached.");}
            else if(collection){
                try{inspectCollection(ref,record,depth);}
                catch(RuntimeException e){record.put("truncated",true);record.put("note","The debugger could not read this collection's storage.");}
            }
            else {Map<String,Object> fields=new LinkedHashMap<>();int count=0;for(Field f:ref.referenceType().allFields()){if(f.isStatic()||f.isSynthetic())continue;if(count++>=40){record.put("truncated",true);break;}try{fields.put(f.name(),val(ref.getValue(f),depth+1));}catch(RuntimeException e){fields.put(f.name(),map("kind","unavailable","type",f.typeName()));}}record.put("fields",fields);}
        }
        return map("kind","reference","type",type,"ref",id);
    }
    static boolean user(Location loc) {
        try{return loc.sourceName().equals(sourceFile) && loc.lineNumber()>0;}catch(AbsentInformationException e){return false;}
    }
    static void recordException(ExceptionEvent event) throws Exception {
        Location location=event.location();
        if(!user(location)){
            Location handler=event.catchLocation();
            if(handler!=null&&!user(handler))return;
            location=null;
            for(StackFrame frame:event.thread().frames()){
                if(user(frame.location())){location=frame.location();break;}
            }
            if(location==null)return;
        }
        ObjectReference exception=event.exception();
        Value detail=field(exception,"detailMessage");
        String message=detail instanceof StringReference text?text.value():"";
        snapshot(event.thread(),location,"exception",null,
            map("type",exception.referenceType().name(),"message",message.substring(0,Math.min(4096,message.length()))));
    }
    static void snapshot(ThreadReference thread,Location location,String event,Value returned,Object exception) throws Exception {
        if(steps.size()>=maxSteps-1){reason="step_limit";status="truncated";return;}
        objects=new LinkedHashMap<>();
        List<Object> frames=new ArrayList<>();
        int depth=thread.frameCount();
        List<StackFrame> observed=depth==0?List.of():thread.frames(0,Math.min(depth,80));
        Map<Integer,RecordedFrame> stack=stacks.computeIfAbsent(thread.uniqueID(),id->new HashMap<>());
        stack.keySet().removeIf(level->level>depth);
        int innermost=-1;
        for(int i=0;i<observed.size()&&frames.size()<50;i++){
            StackFrame frame=observed.get(i);if(!user(frame.location()))continue;
            int level=depth-i;
            if(innermost<0)innermost=level;
            Method method=frame.location().method();
            RecordedFrame stored=stack.get(level);
            if(stored==null||!stored.method().equals(method)||(event.equals("call")&&i==0)){
                stored=new RecordedFrame(method,"f"+(++nextFrame));stack.put(level,stored);
            }
            Map<String,Object> locals=new LinkedHashMap<>();
            if(frame.thisObject()!=null)locals.put("this",val(frame.thisObject(),0));
            try{List<LocalVariable> visible=frame.visibleVariables();Map<LocalVariable,Value> values=frame.getValues(visible.subList(0,Math.min(100,visible.size())));for(LocalVariable local:visible){if(locals.size()>=100)break;locals.put(local.name(),val(values.get(local),0));}}catch(AbsentInformationException e){locals.put("<locals>",map("kind","unavailable","type","unknown","note","No debug information is available."));}
            frames.add(map("id",stored.id(),"name",method.name(),"line",frame.location().lineNumber(),"locals",locals));
        }
        Collections.reverse(frames);
        Map<String,Object> globals=new LinkedHashMap<>();
        for(ReferenceType cls:userClasses){List<Field> fields=new ArrayList<>();for(Field f:cls.allFields())if(f.isStatic()&&!f.isSynthetic())fields.add(f);try{Map<Field,Value> values=cls.getValues(fields);for(Field f:fields)if(globals.size()<100)globals.put(cls.name()+"."+f.name(),val(values.get(f),0));}catch(RuntimeException e){} }
        Map<String,Object> ret=returned==null?null:val(returned,0);
        String threadLabel=thread.name().equals("main")?"Main thread":thread.name();
        threadLabel=threadLabel.substring(0,Math.min(100,threadLabel.length()));
        steps.add(map("index",steps.size(),"event",event,"location",map("file",sourceFile,"line",location.lineNumber(),"phase",event.equals("return")?"after":"before"),"frames",frames,"globals",globals,"objects",objects,"stdout",out.text(8192),"stderr",err.text(8192),"exception",exception,"returnValue",ret,"thread",threadLabel));
        publish(false);
        if(event.equals("return"))stack.remove(innermost);
    }
    static void step(ThreadReference thread) {
        EventRequestManager manager=vm.eventRequestManager();
        for(StepRequest old:new ArrayList<>(manager.stepRequests()))if(old.thread().equals(thread))manager.deleteEventRequest(old);
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
        String classpath=System.getProperty("spandy.classpath",workspace.toAbsolutePath().toString());
        String preview=Boolean.getBoolean("spandy.preview")?" --enable-preview":"";
        params.get("main").setValue("SpandyRun");params.get("options").setValue("-Xmx"+System.getProperty("spandy.heapMiB","192")+"m"+preview+" -Dfile.encoding=UTF-8 -Dspandy.source="+sourceFile+" -Dspandy.entry="+entryClass+" -Dspandy.workspace=\""+workspace.toAbsolutePath()+"\" -XX:+UseSerialGC -XX:CICompilerCount=2 -cp \""+classpath+"\"");params.get("suspend").setValue("true");
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
                else if(event instanceof ExceptionEvent)recordException((ExceptionEvent)event);
            }
            if(!done)events.resume();
        }}catch(VMDisconnectedException e){done=true;}finally{if(!done)try{vm.exit(1);}catch(RuntimeException e){}process.waitFor();out.join(300);err.join(300);}
        if(out.limited||err.limited)Files.writeString(workspace.resolve("output-limited.flag"),"1");
        if(status.equals("completed")&&process.exitValue()!=0){status="failed";reason="runtime_error";}
        Map<String,Object> last=steps.isEmpty()?map("globals",new LinkedHashMap<>(),"objects",new LinkedHashMap<>()):(Map<String,Object>)steps.get(steps.size()-1);
        steps.add(map("index",steps.size(),"event",status.equals("completed")?"completed":"terminated","location",null,"frames",new ArrayList<>(),"globals",last.get("globals"),"objects",last.get("objects"),"stdout",out.text(65536),"stderr",err.text(65536),"exception",null,"note",reason));
        out.close();err.close();
        Files.writeString(workspace.resolve("jdi.json"),json(map("runtimeVersion",System.getProperty("java.version"),"status",status,"terminationReason",reason,"steps",steps)),StandardCharsets.UTF_8);
    }
}
