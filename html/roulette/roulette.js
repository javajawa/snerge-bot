console.log("Roguelike Roulette");

import { elemGenerator } from "https://javajawa.github.io/elems.js/elems.js";

const div = elemGenerator("div");
const span = elemGenerator("span");
const button = elemGenerator("button");

// ===== ===== ===== Wheel Entries ===== ===== ===== //

let entriesState = [];

// TODO: we'll get these from websocket pushes.
// Or maybe not? If we're editing the entries manually,
// wouldn't we want to keep the state purely on frontend in localStorage?
// Which would imply we'd need to do any matching in frontend,
// or we'd need to push the list of entries back to the server for matching
// Having them serverside would let the bot respond to chatters if the submission is not matched
// Separately, I think we do want to track entries that have been removed from the list
// for sake or revive one, revive all, and for maintaining a list of well-known matches
// If we do the well-know matches serverside, we could potentially reuse functionality
// for persistence from the quotes.
// I'm starting to become convinced we want to maintain the list of well-known matches
// and the list of wheel entries separately
const mockEntriesGames = [
  {
    id: "0000",
    weight: 1,
    label: "Deep Rock Survivor",
    aliases: ["Deep Rock", "Rock and Stone", "DRS"],
  },
  { id: "0001", weight: 1, label: "Hades 2", aliases: ["Hades"] },
  { id: "0002", weight: 1, label: "Holocure", aliases: [] },
  { id: "0003", weight: 1, label: "FTL", aliases: ["Faster than Light"] },
  { id: "0004", weight: 1, label: "God of Weapons", aliases: ["GoW"] },
  { id: "0005", weight: 1, label: "Guildrun", aliases: [] },
  { id: "0006", weight: 1, label: "Vampire Survivors", aliases: [] },
];
const mockEntriesDessert = [
  { id: "0000", weight: 1, label: "Pie", aliases: [] },
  { id: "0001", weight: 1, label: "Cake", aliases: [] },
  { id: "0002", weight: 1, label: "Icecream", aliases: ["Ice Cream"] },
];

function processEntries(entries) {
  entriesState = entries;
  EntriesList({ entries });
}

function updateEntry(value, entryId) {
  console.log("updateEntry", { value, entryId });
  // TODO: guard against missing entryId
  entriesState = entriesState.map((entry) =>
    entry.id === entryId
      ? // TODO: remove entry if it drops to zero
        { ...entry, weight: Math.max(1, entry.weight + value) }
      : entry,
  );
  console.log(entriesState);
  EntriesList({ entries: entriesState });
}

// ----- Components

function EntriesList({ entries }) {
  const anchorId = "entries-list";
  const elements = entries.map((entry) => {
    return Entry({ ...entry });
  });
  const oldList = document.getElementById(anchorId);
  const newList = div({ id: anchorId }, elements);
  oldList.parentElement.replaceChild(newList, oldList);
}

function Entry({ label, weight, id }) {
  return div(
    button({ click: () => updateEntry(1, id) }, "➕"),
    button({ click: () => updateEntry(-1, id) }, "➖"),
    ` ${label} - ${weight}`,
  );
}

// ===== ===== ===== Submissions ===== ===== ===== //

let submissionsState = [];

// TODO: we'll get these from websocket pushes
const mockSubmissions = [
  {
    eventId: "0000",
    chatterUsername: "huhwhozat",
    totalWeight: 3,
    weights: [
      { gameId: "0002", label: "Holocure", weight: 2, applied: false },
      { gameId: "0001", label: "Hades 2", weight: 1, applied: false },
    ],
  },
  {
    eventId: "0001",
    chatterUsername: "huhwhozat",
    message: "Lorem ipsum dolor sit amet consectetur adipisicing elit.",
    totalWeight: 6,
    weights: [
      { gameId: undefined, label: "~unknown~", weight: 1, applied: false },
      { gameId: "0001", label: "Hades 2", weight: 5, applied: true },
    ],
  },
];

function processSubmissions(submissions) {
  submissionsState = submissions;
  SubmissionsList({ submissions });
}

function updateSubmission(action, weight, eventId, gameId = undefined) {
  console.log("updateSubmission", { action, eventId, gameId });
  submissionsState = submissionsState.map((submission) =>
    submission.eventId === eventId
      ? gameId
        ? {
            ...submission,
            weights: submission.weights.map((weight) =>
              weight.gameId === gameId ? { ...weight, applied: true } : weight,
            ),
          }
        : { ...submission, applied: true }
      : submission,
  );
  console.log(submissionsState);
  // TODO: update all when total row clicked
  if (action === "confirm" && gameId) {
    // TODO: guard against missing entryId
    updateEntry(weight, gameId);
  }
  SubmissionsList({ submissions: submissionsState });
}

// ----- Components

function SubmissionCard({
  eventId,
  chatterUsername,
  message,
  totalWeight,
  weights,
  applied,
}) {
  return div({ style: "border: 1px solid black;" }, [
    div(chatterUsername),
    div(message ?? "~no message~"),
    ...weights?.map((gameWeight) =>
      div(
        { style: gameWeight.applied ? "text-decoration: line-through;" : "" },
        ...SubmissionGameWeightButtons({
          isConfirmDisabled: gameWeight.applied || !gameWeight.gameId,
          isRejectDisabled: gameWeight.applied,
          onConfirm: () =>
            updateSubmission(
              "confirm",
              gameWeight.weight,
              eventId,
              gameWeight.gameId,
            ),
          onReject: () =>
            updateSubmission(
              "reject",
              gameWeight.weight,
              eventId,
              gameWeight.gameId,
            ),
        }),
        ` ${gameWeight.label} - ${gameWeight.weight}`,
      ),
    ),
    div(
      { style: applied ? "text-decoration: line-through;" : "" },
      ...SubmissionGameWeightButtons({
        // onConfirm: () => updateSubmission("confirm", totalWeight, eventId),
        // onReject: () => updateSubmission("reject", totalWeight, eventId),
        isConfirmDisabled: applied,
        isRejectDisabled: applied,
      }),
      ` Total: ${totalWeight}`,
    ),
  ]);
}

function SubmissionGameWeightButtons({
  onConfirm,
  onReject,
  isConfirmDisabled = false,
  isRejectDisabled = false,
}) {
  return [
    button({ click: onConfirm, disabled: isConfirmDisabled }, "✔️"),
    button({ click: onReject, disabled: isRejectDisabled }, "✖️"),
  ];
}

function SubmissionsList({ submissions }) {
  const anchorId = "submissions-list";
  const elements = submissions.map((submission) => {
    return SubmissionCard({ ...submission });
  });
  const oldList = document.getElementById(anchorId);
  const newList = div({ id: anchorId }, elements);
  oldList.parentElement.replaceChild(newList, oldList);
}

// ===== ===== ===== Main ===== ===== ===== //

processSubmissions(mockSubmissions);
processEntries(mockEntriesGames);
