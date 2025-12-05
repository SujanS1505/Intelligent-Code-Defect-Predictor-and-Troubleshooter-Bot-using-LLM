import java.io.*;
public class JavaResourceLeak {
    public static void main(String[] args) throws Exception {
        FileInputStream in = new FileInputStream("missing.txt"); // BUG: not closed
        byte[] b = new byte[4];
        in.read(b);
        System.out.println(new String(b));
    }
}
