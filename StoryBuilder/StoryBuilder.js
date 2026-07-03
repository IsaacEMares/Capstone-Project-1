// ===== Story Builder =====
// How it works:
// 1. Grab the words the user typed in.
// 2. Pick the template that matches the chosen theme.
// 3. Swap the {placeholders} in the template with the user's words.
// 4. Show the finished story, and optionally save it to localStorage
//    so it's still there when the page is refreshed.

// --- Story templates (the {curly} parts get replaced) ---
const templates = {
    adventure: {
        title: "The Quest of {heroName}",
        text: "Once upon a time, {heroName} and their loyal sidekick {sidekick} " +
              "set off on a journey to {place}. Along the way they discovered " +
              "{object}, which turned out to be surprisingly {adjective}. " +
              "With it in hand, no mountain was too tall and no river too wide. " +
              "The people of {place} still tell stories about the {adjective} duo to this day."
    },
    scifi: {
        title: "{heroName} and the Signal from {place}",
        text: "In the year 3025, Captain {heroName} picked up a strange signal " +
              "coming from {place}. Co-pilot {sidekick} plotted the course while " +
              "the ship's scanners locked onto {object} floating in deep space. " +
              "It glowed with a {adjective} light no human had ever seen. " +
              "\"Whatever happens,\" said {heroName}, \"we're bringing it home.\""
    },
    spooky: {
        title: "The {adjective} House in {place}",
        text: "Nobody in {place} ever went near the old house on the hill. " +
              "But one foggy night, {heroName} and {sidekick} crept up to its door. " +
              "Inside, sitting on a dusty table, was {object} — and it was moving. " +
              "A {adjective} whisper filled the room: \"You should not have come...\" " +
              "{sidekick} barked once, and the whisper was never heard again."
    }
};

// --- Random words for the "Surprise Me" button ---
const randomWords = {
    heroName: ["Isaac", "Luna", "Captain Torres", "Max", "Zelda"],
    sidekick: ["Snoopy", "a talking cactus", "Robo-Cat", "Grandma Rosa", "a tiny dragon"],
    place: ["Corpus Christi", "the Moon", "a haunted mall", "Tokyo", "the Grand Canyon"],
    object: ["a glowing keyboard", "a map made of cheese", "an ancient game console", "a singing sword", "a jar of stars"],
    adjective: ["sparkly", "mysterious", "ridiculous", "ancient", "slippery"]
};

// --- Grab the elements we need from the page ---
const buildBtn = document.getElementById("buildBtn");
const surpriseBtn = document.getElementById("surpriseBtn");
const saveBtn = document.getElementById("saveBtn");
const clearBtn = document.getElementById("clearBtn");
const resultSection = document.getElementById("resultSection");
const storyTitle = document.getElementById("storyTitle");
const storyText = document.getElementById("storyText");
const savedList = document.getElementById("savedList");

const fieldIds = ["heroName", "sidekick", "place", "object", "adjective"];

// Replace every {placeholder} in a template string with the user's words
function fillTemplate(templateString, words) {
    let result = templateString;
    for (const key of fieldIds) {
        // split/join replaces ALL occurrences, not just the first one
        result = result.split("{" + key + "}").join(words[key]);
    }
    return result;
}

// Read the input boxes; fall back to fun defaults if a box is empty
function getWords() {
    const words = {};
    for (const id of fieldIds) {
        const typed = document.getElementById(id).value.trim();
        words[id] = typed !== "" ? typed : "???";
    }
    return words;
}

// Build the story and show it on the page
function buildStory() {
    const theme = document.getElementById("theme").value;
    const words = getWords();
    const template = templates[theme];

    storyTitle.textContent = fillTemplate(template.title, words);
    storyText.textContent = fillTemplate(template.text, words);
    resultSection.hidden = false;
}

// Pick a random item from an array
function pickRandom(list) {
    return list[Math.floor(Math.random() * list.length)];
}

// Fill every input with a random word, then build the story
function surpriseMe() {
    for (const id of fieldIds) {
        document.getElementById(id).value = pickRandom(randomWords[id]);
    }
    buildStory();
}

// --- Saving stories with localStorage ---

function loadSavedStories() {
    const raw = localStorage.getItem("savedStories");
    return raw ? JSON.parse(raw) : [];
}

function renderSavedStories() {
    const stories = loadSavedStories();
    savedList.innerHTML = "";
    if (stories.length === 0) {
        const li = document.createElement("li");
        li.textContent = "No saved stories yet — build one above!";
        savedList.appendChild(li);
        return;
    }
    for (const story of stories) {
        const li = document.createElement("li");
        const strong = document.createElement("strong");
        strong.textContent = story.title;
        li.appendChild(strong);
        li.appendChild(document.createTextNode(" — " + story.text));
        savedList.appendChild(li);
    }
}

function saveCurrentStory() {
    const stories = loadSavedStories();
    stories.push({
        title: storyTitle.textContent,
        text: storyText.textContent
    });
    localStorage.setItem("savedStories", JSON.stringify(stories));
    renderSavedStories();
}

function clearSavedStories() {
    localStorage.removeItem("savedStories");
    renderSavedStories();
}

// --- Hook up the buttons ---
buildBtn.addEventListener("click", buildStory);
surpriseBtn.addEventListener("click", surpriseMe);
saveBtn.addEventListener("click", saveCurrentStory);
clearBtn.addEventListener("click", clearSavedStories);

// Show any stories that were saved on a previous visit
renderSavedStories();
