public class JavaOverflow {
    public static void main(String[] args) {
        int a = Integer.MAX_VALUE;
        int b = a + 1; // BUG: overflow wraps to negative
        System.out.println(b);
    }
}
