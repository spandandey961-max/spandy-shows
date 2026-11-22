import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.regex.*;

/** Input is supplied only when the real runtime requests more bytes. */
public class SpandyRun {
    static final String SOURCE_FILE = System.getProperty("spandy.source", "Main.java");
    static void replace(Path temporary, Path target) throws IOException {
        for (int attempt=0;;attempt++) try { Files.move(temporary,target,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE); return; }
        catch (FileSystemException e) { if(attempt>=49) throw e; pause(); }
    }
    static void remove(Path path) throws IOException {
        for (int attempt=0;;attempt++) try { Files.deleteIfExists(path); return; }
        catch (FileSystemException e) { if(attempt>=49) throw e; pause(); }
    }
    static void pause() throws IOException {
        try { Thread.sleep(5); } catch(InterruptedException e) { Thread.currentThread().interrupt(); throw new IOException("Input interrupted.",e); }
    }
    static class LiveInput extends InputStream {
        final Path workspace = Path.of(System.getProperty("spandy.workspace"));
        final String[] source;
        byte[] buffer;
        int position = 0, sequence = 0;
        boolean eof = false;
        LiveInput() throws IOException {
            source = Files.readString(workspace.resolve(SOURCE_FILE)).split("\\R", -1);
            buffer = Files.readAllBytes(workspace.resolve("stdin.txt"));
        }
        void fill() throws IOException {
            int line = 1;
            for (StackTraceElement frame : Thread.currentThread().getStackTrace())
                if (SOURCE_FILE.equals(frame.getFileName()) && frame.getLineNumber() > 0) { line = frame.getLineNumber(); break; }
            String code = line <= source.length ? source[line-1] : "";
            String kind = code.matches(".*\\b(?:hasN|n)ext(?:Int|Long|Short|Byte|BigInteger)\\s*\\(.*") ? "integer"
                : code.matches(".*\\b(?:hasN|n)ext(?:Float|Double|BigDecimal)\\s*\\(.*") ? "number"
                : code.matches(".*\\bcharAt\\s*\\(\\s*0\\s*\\).*") ? "character" : "text";
            if (++sequence > 512) throw new IOException("The 512-response input limit was reached.");
            // Publish the exact recorded prefix before exposing this real read.
            if (Files.exists(workspace.resolve("visualize.flag"))) {
                Path checkpoint=workspace.resolve("checkpoint-request");
                Files.writeString(checkpoint, "1");
                while (Files.exists(checkpoint)) try { Thread.sleep(5); } catch (InterruptedException e) { throw new IOException("Input interrupted.", e); }
            }
            Path request = workspace.resolve("input-request.json"), temporary = workspace.resolve("input-request.json.tmp");
            Files.writeString(temporary, "{\"id\":"+sequence+",\"line\":"+line+",\"type\":\""+kind+"\"}");
            replace(temporary, request);
            Path response = workspace.resolve("input-response-"+sequence+".json");
            while (!Files.exists(response)) try { Thread.sleep(25); } catch (InterruptedException e) { throw new IOException("Input interrupted.", e); }
            // The API also writes a raw UTF-8 response, avoiding a second JSON parser in the JVM.
            buffer = Files.readAllBytes(workspace.resolve("input-text-"+sequence+".txt"));
            eof = buffer.length == 0;
            position = 0;
            remove(request); remove(response);
            remove(workspace.resolve("input-text-"+sequence+".txt"));
        }
        @Override public synchronized int read() throws IOException {
            if (!eof && position == buffer.length) fill();
            return eof ? -1 : buffer[position++] & 255;
        }
        @Override public synchronized int read(byte[] bytes, int offset, int length) throws IOException {
            java.util.Objects.checkFromIndexSize(offset, length, bytes.length);
            if (length == 0) return 0;
            if (!eof && position == buffer.length) fill();
            if (eof) return -1;
            int count = Math.min(length, buffer.length-position);
            System.arraycopy(buffer, position, bytes, offset, count); position += count; return count;
        }
    }
    public static void main(String[] args) throws Throwable {
        Path workspace = Path.of(System.getProperty("spandy.workspace"));
        if (Files.exists(workspace.resolve("interactive.flag"))) System.setIn(new LiveInput());
        String[] programArgs = Files.readAllLines(workspace.resolve("args.txt")).toArray(String[]::new);
        Class<?> program = Class.forName(System.getProperty("spandy.entry", "Main"));
        java.lang.reflect.Method main;
        try {
            main=program.getDeclaredMethod("main", String[].class);
            if(java.lang.reflect.Modifier.isPrivate(main.getModifiers())||main.getReturnType()!=void.class)
                main=program.getDeclaredMethod("main");
        } catch(NoSuchMethodException missingArgs) {
            main=program.getDeclaredMethod("main");
        }
        int modifiers = main.getModifiers();
        if (java.lang.reflect.Modifier.isPrivate(modifiers) || main.getReturnType() != void.class)
            throw new NoSuchMethodException("Expected a non-private void main, with either no arguments or String[] args.");
        main.setAccessible(true);
        try {
            Object receiver=null;
            if(!java.lang.reflect.Modifier.isStatic(modifiers)){
                var constructor=program.getDeclaredConstructor();
                constructor.setAccessible(true);
                receiver=constructor.newInstance();
            }
            if(main.getParameterCount()==0)main.invoke(receiver);
            else main.invoke(receiver,(Object) programArgs);
        }
        catch (java.lang.reflect.InvocationTargetException e) { throw e.getCause(); }
    }
}
