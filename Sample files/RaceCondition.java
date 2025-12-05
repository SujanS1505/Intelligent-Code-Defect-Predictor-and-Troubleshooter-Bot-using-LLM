public class Counter {
    private int count = 0;
    public void increment() {
        count = count + 1; // Not synchronized → Race condition
    }
    public int getCount() { return count; }
}
