// SPDX-FileCopyrightText: 2022 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import { elemGenerator } from "https://javajawa.github.io/elems.js/elems.js";

const div = elemGenerator("div");
const summary = elemGenerator("summary");
const details = elemGenerator("details");
const span = elemGenerator("code");

function search() {
	const term = document.getElementById("search")?.value || "";

	if (term === "") {
		return;
	}

	const url = new URL(window.location);
	url.search = "?search=" + term;
	window.history.replaceState({"search": term}, window.title, url)

	fetch('search', {method: 'POST', body: term})
		.then(r => r.json())
		.then(r => Object.entries(r))
		.then(r => r.map(([word, refs]) =>
			details(
				r.length === 1 ? {"open": "open"} : null,
				summary(word, " (", refs.length.toString(), ")"),
				refs.map(ref => details(
					summary(ref.source, " - ", ref.text),
					ref.tokens.map(token => [span(token), " "])
				))
			)
		))
		.then(elements => {
			const oldList = document.getElementById("results");
			const newList = div({"id": "results"}, elements);
			oldList.parentElement.replaceChild(newList, oldList);
		});
}

const searchBox = document.getElementById("search");
const debounce = null;
searchBox.addEventListener("change", () => {window.clearTimeout(debounce); search()});
searchBox.addEventListener("keyup", () => {window.clearTimeout(debounce); window.setTimeout(search, 500)});
searchBox.value = (new URLSearchParams(window.location.search).get("search")) || "";
search()
