public class JavaSubstringOOB {
    public static void main(String[] args) {
        String s = "abc";
        System.out.println(s.substring(0, 5)); // BUG: StringIndexOutOfBoundsException
    }
}
