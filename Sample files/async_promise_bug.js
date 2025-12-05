async function fetchData() {
  const result = fetch('https://example.com/data'); // Missing await
  console.log(await result.json()); // TypeError: result.json is not a function
}
fetchData();
