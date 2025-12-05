// BuggyExample.java

class BuggyExample {
    public static void main(String[] args) {
        String data = null;
        
        // Bug 1: NullPointerException
        // This attempts to call a method on a null object.
        int length = data.length(); 
        System.out.println("Length: " + length);

        // Bug 2: Division by Zero
        int x = 5;
        int y = 0;
        int result = x / y;
        System.out.println("Result: " + result);
    }
}