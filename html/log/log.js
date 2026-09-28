// SPDX-FileCopyrightText: 2026 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import { elemGenerator } from "https://javajawa.github.io/elems.js/elems.js";

const p = elemGenerator("p");
const span = elemGenerator("code");

const results = document.getElementById("results");

function loadHistory() {
	fetch('history', {method: 'POST'})
		.then(r => r.json())
		.then(r => r.map(eventToHtml))
		.then(r => r.map(e => results.insertBefore(e, results.firstElementChild)))
		.then(() => websocket());
}

const eventToHtml = ({time, level, message}) => p(
	(new Date(time)).toLocaleString(),
	" ", span(level.toString()), " ",
	message,
);

function websocket() {
	const socket = new WebSocket("stream");
	socket.addEventListener("message", e => {
		const data = JSON.parse(e.data);
		results.insertBefore(eventToHtml(data), results.firstElementChild);
	})
}

loadHistory();
