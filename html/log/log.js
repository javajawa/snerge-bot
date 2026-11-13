// SPDX-FileCopyrightText: 2026 Benedict Harcourt <ben.harcourt@harcourtprogramming.co.uk>
//
// SPDX-License-Identifier: BSD-2-Clause

import { elemGenerator } from "https://javajawa.github.io/elems.js/elems.js";

const div = elemGenerator("div");
const br = elemGenerator("br");
const code = elemGenerator("code");
const dtime = elemGenerator("time");
const section = elemGenerator("section");

const results = document.getElementById("results");

function loadHistory() {
	fetch('history', {method: 'POST'})
		.then(r => r.json())
		.then(r => r.map(eventToHtml))
		.then(r => r.map(e => results.insertBefore(e, results.firstElementChild)))
		.then(() => websocket());
}

const tsToHtml = (time) => {
	const date = new Date(time * 1000);

	return dtime(
		date.toLocaleTimeString(),
		{"datetime": date.toISOString(), "title": date.toISOString()}
	);
}

const eventToHtml = ({time, logger, level, message}) => section(
	div(
		tsToHtml(time),
		" ", code(level.toString()),
		br(),
		code(logger.toString()),
		{"style": "display: inline-block; width: 9rem; font-size: 70%; float: left"},
	),
	code(message, {"style": "min-height: 2rem"}),
	{"style": "border-bottom: 1px solid #ccc, margin: 0"},
);

function websocket() {
	const socket = new WebSocket("stream");
	socket.addEventListener("message", e => {
		const data = JSON.parse(e.data);
		results.insertBefore(eventToHtml(data), results.firstElementChild);
	})
	window.setInterval(() => socket.send("ping"), 5000);
}

document.getElementById("reconnect").addEventListener("click", e => {
	e.preventDefault();
	fetch('reconnect', {method: 'POST'}).then(r => r.status !== 202 ? alert("Something went wrong...") : null);
});

loadHistory();
