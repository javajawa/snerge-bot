// SPDX-FileCopyrightText: 2022 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import { elemGenerator } from "https://javajawa.github.io/elems.js/elems.js";

const p = elemGenerator("p");
const li = elemGenerator("li");
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

	fetch('predict', {method: 'POST', body: term})
		.then(r => r.json())
		.then(({input, output}) => details(
			{"open": "open"},
			summary(output.text),
			p(input.text, " - ", input.tokens.map(token => [span(token), " "])),
			p(output.tokens.map(token => [span(token), " "])),
		))
		.then(element => {
			const list = document.getElementById("results");
			list.firstElementChild?.removeAttribute("open");
			list.insertBefore(element, list.firstElementChild || null);
		});
}

const searchBox = document.getElementById("search");
let debounce = null;
searchBox.addEventListener("change", () => {window.clearTimeout(debounce); search()});
searchBox.addEventListener("keyup", () => {window.clearTimeout(debounce); debounce = window.setTimeout(search, 1000)});
searchBox.value = (new URLSearchParams(window.location.search).get("search")) || "";
search()
