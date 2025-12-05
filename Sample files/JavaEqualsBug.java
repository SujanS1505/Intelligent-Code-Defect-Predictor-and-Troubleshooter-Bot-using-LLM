public class JavaEqualsBug {
    public static void main(String[] args) {
        String a = new String("hello");
        String b = new String("hello");
        if (a == b) { // BUG: reference equality instead of content equality
            System.out.println("equal");
        } else {
            System.out.println("not equal"); // unexpected for beginners
        }
    }
}
