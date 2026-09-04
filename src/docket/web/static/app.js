const mermaidTheme = () =>
  document.documentElement.dataset.theme === "dark" ? "dark" : "default";

const initMermaid = () =>
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "loose",
    maxTextSize: 500000,
    maxEdges: 5000,
    theme: mermaidTheme(),
  });

initMermaid();

const renderDiagrams = (root) => {
  const nodes = [...root.querySelectorAll(".mermaid")];
  for (const node of nodes) {
    if (!node.dataset.source) node.dataset.source = node.textContent;
  }
  mermaid.run({ nodes });
};

document.body.addEventListener("htmx:afterSwap", (event) => {
  renderDiagrams(event.detail.target);
});

window.toggleTheme = () => {
  const root = document.documentElement;
  root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
  try {
    localStorage.setItem("docket-theme", root.dataset.theme);
  } catch (error) {}
  initMermaid();
  for (const node of document.querySelectorAll(".mermaid")) {
    node.textContent = node.dataset.source || node.textContent;
    node.removeAttribute("data-processed");
  }
  renderDiagrams(document);
};
