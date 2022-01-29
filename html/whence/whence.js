import { elemGenerator } from "https://javajawa.github.io/elems.js/elems.js";

const ul = elemGenerator("ul");
const li = elemGenerator("li");
const a = elemGenerator("a");

function search() {
	const term = document.getElementById("search")?.value || "";
	fetch('search', {method: 'POST', body: term})
		.then(r => r.json())
		.then(r => Object.entries(r))
		.then(r => r.forEach(([word, refs]) => {
			document.body.appendChild(
				ul(li(word), ul(refs.map(ref => li(ref))))
			);
		}));
}

document.getElementById("search").addEventListener("change", search);
