// SPDX-FileCopyrightText: 2022 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import { elemGenerator, documentFragment } from "https://javajawa.github.io/elems.js/elems.js";

const div = elemGenerator("div");
const summary = elemGenerator("summary");
const details = elemGenerator("details");
const span = elemGenerator("code");

function search() {
	const term = document.getElementById("search")?.value || "";
	fetch('search', {method: 'POST', body: term})
		.then(r => r.json())
		.then(r => Object.entries(r))
		.then(r => r.map(([word, refs]) =>
			details(
				{"open": "open"},
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

document.getElementById("search").addEventListener("change", search);
document.getElementById("search").addEventListener("keyup", search);
