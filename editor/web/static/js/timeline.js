function secondsToPixels(app, seconds) {
    return Number(seconds || 0) * app.state.zoom;
}

function pixelsToSeconds(app, pixels) {
    return Number(pixels || 0) / app.state.zoom;
}

function formatTime(seconds) {
    const safe = Math.max(0, Number(seconds || 0));
    return `${safe.toFixed(1)}s`;
}

function timelineWidth(app) {
    const duration = Math.max(app.projectDuration(), 30);
    return Math.max(1600, Math.ceil(secondsToPixels(app, duration + 2)));
}

function clipMarkup(app, clip) {
    const node = document.createElement("div");
    node.className = "clip";
    node.dataset.clipId = clip.id;
    node.dataset.kind = clip.type || "video";
    if (app.state.selection.includes(clip.id)) {
        node.classList.add("selected");
    }
    if (clip.groupId) {
        node.classList.add("grouped");
    }

    node.style.left = `${secondsToPixels(app, clip.start)}px`;
    node.style.width = `${Math.max(42, secondsToPixels(app, clip.duration))}px`;
    node.innerHTML = `
        <div class="clip-handle start" data-resize="start"></div>
        <div class="clip-name">${clip.text || clip.name || "Clip"}</div>
        <div class="clip-duration">${formatTime(clip.duration)}</div>
        <div class="clip-handle end" data-resize="end"></div>
    `;
    return node;
}

function bindClipEvents(app, node, clip, track) {
    node.addEventListener("click", (event) => {
        event.stopPropagation();
        app.selectClip(clip.id, event.shiftKey || event.ctrlKey || event.metaKey);
    });

    node.addEventListener("pointerdown", (event) => {
        const handle = event.target.closest("[data-resize]");
        const startX = event.clientX;
        const originalStart = Number(clip.start);
        const originalDuration = Number(clip.duration);
        const trackIndex = app.findTrackIndex(track.id);
        const mode = handle ? `resize-${handle.dataset.resize}` : "move";
        node.setPointerCapture?.(event.pointerId);

        const groupIds = app.dragGroup(clip.id);
        const originMap = new Map(
            groupIds.map((id) => {
                const item = app.findClip(id);
                return [id, { start: Number(item.clip.start), duration: Number(item.clip.duration), sourceIn: Number(item.clip.sourceIn || 0) }];
            }),
        );

        const onMove = (moveEvent) => {
            const deltaSeconds = pixelsToSeconds(app, moveEvent.clientX - startX);
            if (mode === "move") {
                groupIds.forEach((id) => {
                    const found = app.findClip(id);
                    const origin = originMap.get(id);
                    found.clip.start = Math.max(0, origin.start + deltaSeconds);
                });
            } else if (mode === "resize-start") {
                const nextStart = Math.max(0, originalStart + deltaSeconds);
                const clipEnd = originalStart + originalDuration;
                const nextDuration = Math.max(0.2, clipEnd - nextStart);
                clip.start = nextStart;
                clip.duration = nextDuration;
                clip.sourceIn = Math.max(0, Number(clip.sourceIn || 0) + (nextStart - originalStart));
            } else if (mode === "resize-end") {
                clip.duration = Math.max(0.2, originalDuration + deltaSeconds);
            }

            const rowHeight = 56;
            const timelineBox = app.refs.timelineTracks.getBoundingClientRect();
            const relativeY = moveEvent.clientY - timelineBox.top;
            const nextTrackIndex = Math.max(0, Math.min(app.state.project.tracks.length - 1, Math.floor(relativeY / rowHeight)));
            if (mode === "move" && nextTrackIndex !== trackIndex) {
                app.moveClipsToTrack(groupIds, app.state.project.tracks[nextTrackIndex].id);
            }

            app.render();
        };

        const onUp = () => {
            window.removeEventListener("pointermove", onMove);
            window.removeEventListener("pointerup", onUp);
            app.render();
        };

        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
    });
}

function renderRuler(app) {
    const duration = Math.max(app.projectDuration(), 30);
    const width = timelineWidth(app);
    const ruler = app.refs.timelineRuler;
    ruler.innerHTML = "";
    ruler.style.width = `${width}px`;

    for (let second = 0; second <= duration + 1; second += 1) {
        const mark = document.createElement("div");
        mark.className = "ruler-mark";
        mark.style.left = `${secondsToPixels(app, second)}px`;
        ruler.appendChild(mark);

        const label = document.createElement("div");
        label.className = "ruler-label";
        label.style.left = `${secondsToPixels(app, second)}px`;
        label.textContent = `${second}s`;
        ruler.appendChild(label);
    }
}

function renderTrackHeaders(app) {
    const headers = app.refs.trackHeaderList;
    headers.innerHTML = "";

    app.state.project.tracks.forEach((track) => {
        const node = document.createElement("div");
        node.className = "track-header";
        node.innerHTML = `
            <div class="track-title-row">
                <div class="track-title">${track.name}</div>
                <div class="track-actions">
                    <button class="track-toggle" data-toggle="lock">${track.locked ? "L" : "U"}</button>
                    <button class="track-toggle" data-toggle="hide">${track.hidden ? "H" : "S"}</button>
                </div>
            </div>
            <div class="track-meta">${track.kind.toUpperCase()}</div>
        `;
        node.querySelectorAll(".track-toggle").forEach((button) => {
            button.addEventListener("click", () => {
                const mode = button.dataset.toggle;
                if (mode === "lock") {
                    track.locked = !track.locked;
                } else {
                    track.hidden = !track.hidden;
                }
                app.render();
            });
        });
        headers.appendChild(node);
    });
}

function renderTrackRows(app) {
    const rows = app.refs.timelineTracks;
    rows.innerHTML = "";
    rows.style.width = `${timelineWidth(app)}px`;

    app.state.project.tracks.forEach((track) => {
        const row = document.createElement("div");
        row.className = "track-row";
        row.dataset.trackId = track.id;

        row.addEventListener("dragover", (event) => {
            event.preventDefault();
            row.classList.add("drag-over");
        });
        row.addEventListener("dragleave", () => row.classList.remove("drag-over"));
        row.addEventListener("drop", (event) => {
            event.preventDefault();
            row.classList.remove("drag-over");
            const assetId = event.dataTransfer.getData("text/asset-id");
            const textPreset = event.dataTransfer.getData("text/text-preset");
            const timelineRect = app.refs.timelineScroll.getBoundingClientRect();
            const offsetX = event.clientX - timelineRect.left + app.refs.timelineScroll.scrollLeft;
            const start = Math.max(0, pixelsToSeconds(app, offsetX));
            if (assetId) {
                app.addAssetClip(assetId, track.id, start);
            } else if (textPreset) {
                app.addTextClip(textPreset, track.id, start);
            }
        });

        row.addEventListener("click", (event) => {
            if (event.target !== row) {
                return;
            }
            const rect = app.refs.timelineScroll.getBoundingClientRect();
            const offsetX = event.clientX - rect.left + app.refs.timelineScroll.scrollLeft;
            app.seekTo(pixelsToSeconds(app, offsetX));
            app.clearSelection();
        });

        track.clips.forEach((clip) => {
            const clipNode = clipMarkup(app, clip);
            bindClipEvents(app, clipNode, clip, track);
            row.appendChild(clipNode);
        });

        rows.appendChild(row);
    });
}

export function renderTimeline(app) {
    renderRuler(app);
    renderTrackHeaders(app);
    renderTrackRows(app);
    app.refs.playheadLine.style.left = `${secondsToPixels(app, app.state.playhead)}px`;
}
