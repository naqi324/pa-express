import "./style.css";

const root = document.querySelector<HTMLDivElement>("#app");

if (root === null) {
  throw new Error("Missing #app root element");
}

root.innerHTML = `
  <main>
    <h1>Prior Auth Express</h1>
    <p>Prior authorization, start to decision.</p>
  </main>
`;
