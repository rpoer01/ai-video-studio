import { previewFontSizeForStyle, previewScaleForCanvas, previewStrokeWidthForStyle } from "./styleScale.js";

function findTrack(state, kind) {
    return state.project.tracks.find((track) => track.kind === kind && !track.hidden);
}

function activeClips(track, time) {
    if (!track) {
        return [];
    }
    return track.clips.filter((clip) => {
        if (clip.hidden) {
            return false;
        }
        const start = Number(clip.start || 0);
        const end = start + Number(clip.duration || 0);
        return time >= start && time <= end;
    });
}

function topVisualClip(state, time) {
    const visibleTracks = state.project.tracks.filter(
        (track) => (track.kind === "video" || track.kind === "image") && !track.hidden,
    );
    for (let i = 0; i < visibleTracks.length; i += 1) {
        const track = visibleTracks[i];
        const match = activeClips(track, time).find((clip) => !clip.hidden);
        if (match) {
            return match;
        }
    }
    return null;
}

function applyVideoSource(app, clip) {
    const video = app.refs.previewVideo;
    const image = app.refs.previewImage;
    const empty = app.refs.previewEmpty;

    if (!clip || !clip.sourceUrl) {
        video.pause();
        video.removeAttribute("src");
        video.load();
        image.removeAttribute("src");
        image.classList.add("hidden");
        video.classList.remove("hidden");
        empty.classList.remove("hidden");
        return;
    }

    empty.classList.add("hidden");
    if (clip.type === "image") {
        video.pause();
        video.classList.add("hidden");
        image.classList.remove("hidden");
        if (image.dataset.assetId !== clip.assetId) {
            image.dataset.assetId = clip.assetId || "";
            image.src = clip.sourceUrl;
        }
        return;
    }

    image.classList.add("hidden");
    video.classList.remove("hidden");
    if (video.dataset.assetId !== clip.assetId) {
        video.dataset.assetId = clip.assetId || "";
        video.src = clip.sourceUrl;
        video.load();
    }

    const mediaTime = Math.max(0, Number(clip.sourceIn || 0) + (app.state.playhead - Number(clip.start || 0)));
    if (Number.isFinite(video.duration)) {
        const delta = Math.abs(video.currentTime - mediaTime);
        if (delta > 0.25) {
            video.currentTime = Math.min(video.duration, mediaTime);
        }
    }

    if (app.state.isPlaying && video.paused) {
        video.play().catch(() => {});
    }
    if (!app.state.isPlaying && !video.paused) {
        video.pause();
    }
}

function colorForWord(word, active, style) {
    if (active) {
        return style.highlightColor || "#2dd4bf";
    }
    return style.color || "#ffffff";
}

function appendWordSpans(node, clip) {
    const style = clip.style || {};
    const localTime = Math.max(0, Number(clip._previewTime || 0) - Number(clip.start || 0));
    const words = Array.isArray(clip.words) ? clip.words : [];
    if (!words.length) {
        node.textContent = clip.text || clip.name || "";
        return;
    }

    words.forEach((word, index) => {
        const text = word.text || word.word || "";
        const active = localTime >= Number(word.start || 0) && localTime <= Number(word.end || 0);
        const span = document.createElement("span");
        span.className = "caption-word";
        span.dataset.lang = word.lang || "other";
        span.style.setProperty("--word-color", colorForWord(word, active, style));
        if (active) {
            span.classList.add("active");
        }
        span.textContent = text;
        node.appendChild(span);
        const next = words[index + 1];
        if (next && !(word.lang === "th" && next.lang === "th")) {
            node.appendChild(document.createTextNode(" "));
        }
    });
}

function renderCaption(clip, time) {
    const style = clip.style || {};
    const node = document.createElement("div");
    node.className = "preview-caption";
    node.dataset.animation = style.animation || "none";
    clip._previewTime = time;
    appendWordSpans(node, clip);
    delete clip._previewTime;
    node.style.top = `${Number(style.y ?? 82)}%`;
    node.style.left = `${Number(style.x ?? 50)}%`;
    node.style.color = style.color || "#ffffff";
    const canvasWidth = Math.max(1, Number(app.refs.previewOverlay.getBoundingClientRect().width || 1));
    const previewScale = previewScaleForCanvas(canvasWidth);
    const fontSize = previewFontSizeForStyle(style, app.state.project);
    const strokeWidth = previewStrokeWidthForStyle(style, app.state.project);
    node.style.webkitTextStroke = `${Math.max(0.75, strokeWidth * previewScale)}px ${style.strokeColor || "#000000"}`;
    node.style.fontSize = `${Math.max(8, fontSize * previewScale)}px`;
    node.style.opacity = String(Number(style.opacity ?? 1));
    node.style.fontFamily = "Kanit, Inter, sans-serif";
    return node;
}

export function updatePreview(app) {
    const time = app.state.playhead;
    applyVideoSource(app, topVisualClip(app.state, time));

    const overlay = app.refs.previewOverlay;
    overlay.innerHTML = "";

    app.state.project.tracks
        .filter((track) => (track.kind === "subtitle" || track.kind === "effect") && !track.hidden)
        .forEach((track) => {
            activeClips(track, time).forEach((clip) => {
                overlay.appendChild(renderCaption(clip, time));
            });
        });
}
