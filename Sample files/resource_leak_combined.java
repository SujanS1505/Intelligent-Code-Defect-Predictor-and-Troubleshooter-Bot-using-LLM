import java.io.*;
public class ResourceLeak {
    public static void main(String[] args) throws Exception {
        BufferedReader br = new BufferedReader(new FileReader("data.txt"));
        System.out.println(br.readLine());
        // BUG: not closed
    }
}
