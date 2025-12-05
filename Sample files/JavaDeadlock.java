public class JavaDeadlock {
    private static final Object A = new Object();
    private static final Object B = new Object();
    public static void main(String[] args) {
        new Thread(() -> { synchronized(A){ sleep(); synchronized(B){} } }).start();
        new Thread(() -> { synchronized(B){ sleep(); synchronized(A){} } }).start();
    }
    static void sleep(){ try{ Thread.sleep(10);}catch(Exception e){} }
}
