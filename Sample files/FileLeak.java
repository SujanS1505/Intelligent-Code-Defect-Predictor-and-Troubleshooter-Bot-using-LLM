import java.io.*;
public class FileLeak {
    public static void main(String[] args) throws Exception {
        FileReader fr = new FileReader("data.txt"); // never closed
        System.out.println((char)fr.read());
    }
}
