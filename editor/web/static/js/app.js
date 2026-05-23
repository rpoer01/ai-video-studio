import {
    connectRealtime,
    exportProject,
    listProjects,
    loadProject,
    requestAutoSubtitle,
    saveProject,
    uploadMedia,
} from "./api.js";
import { updatePreview } from "./preview.js";
import { renderTimeline } from "./timeline.js";

function uid(prefix = "id") {
    return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function createTrack(kind, name) {
    return {
        id: uid("track"),
        kind,
        name,
        locked: false,
        hidden: false,
        clips: [],
    };
}

function createProject() {
    return {
        id: uid("project"),
        name: "Untitled Project",
        fps: 30,
        resolution: { width: 1080, height: 1920 },
        assets: [],
        tracks: [
            createTrack("video", "Video"),
            createTrack("video", "Overlay"),
            createTrack("subtitle", "Subtitle"),
            createTrack("effect", "Text"),
            createTrack("audio", "Audio"),
        ],
    };
}

const refs = {
    railTabs: Array.from(document.querySelectorAll(".rail-tab")),
    sidebarViews: Array.from(document.querySelectorAll(".sidebar-view")),
    textOnlyFields: Array.from(document.querySelectorAll(".text-only-field")),
    presetCards: Array.from(document.querySelectorAll(".preset-card")),
    assetList: document.getElementById("asset-list"),
    assetCount: document.getElementById("asset-count"),
    projectNameView: document.getElementById("project-name-view"),
    projectDurationView: document.getElementById("project-duration-view"),
    timelineZoomView: document.getElementById("timeline-zoom-view"),
    previewVideo: document.getElementById("preview-video"),
    previewImage: document.getElementById("preview-image"),
    previewOverlay: document.getElementById("preview-overlay"),
    previewEmpty: document.getElementById("preview-empty"),
    playPauseBtn: document.getElementById("play-pause-btn"),
    rewindBtn: document.getElementById("rewind-btn"),
    forwardBtn: document.getElementById("forward-btn"),
    playheadSlider: document.getElementById("playhead-slider"),
    timecodeView: document.getElementById("timecode-view"),
    trackHeaderList: document.getElementById("track-header-list"),
    timelineScroll: document.getElementById("timeline-scroll"),
    timelineRuler: document.getElementById("timeline-ruler"),
    timelineTracks: document.getElementById("timeline-tracks"),
    playheadLine: document.getElementById("playhead-line"),
    editorStatus: document.getElementById("editor-status"),
    selectionKind: document.getElementById("selection-kind"),
    inspectorEmpty: document.getElementById("inspector-empty"),
    inspectorForm: document.getElementById("inspector-form"),
    clipNameInput: document.getElementById("clip-name-input"),
    clipTextInput: document.getElementById("clip-text-input"),
    clipStartInput: document.getElementById("clip-start-input"),
    clipDurationInput: document.getElementById("clip-duration-input"),
    clipXInput: document.getElementById("clip-x-input"),
    clipYInput: document.getElementById("clip-y-input"),
    clipFontSizeInput: document.getElementById("clip-font-size-input"),
    clipOpacityInput: document.getElementById("clip-opacity-input"),
    clipColorInput: document.getElementById("clip-color-input"),
    clipStrokeColorInput: document.getElementById("clip-stroke-color-input"),
    clipAnimationInput: document.getElementById("clip-animation-input"),
    applyInspectorBtn: document.getElementById("apply-inspector-btn"),
    newProjectBtn: document.getElementById("new-project-btn"),
    saveProjectBtn: document.getElementById("save-project-btn"),
    loadProjectBtn: document.getElementById("load-project-btn"),
    mediaUploadInput: document.getElementById("media-upload-input"),
    addTextBtn: document.getElementById("add-text-btn"),
    autoSubtitleBtn: document.getElementById("auto-subtitle-btn"),
    splitBtn: document.getElementById("split-btn"),
    duplicateBtn: document.getElementById("duplicate-btn"),
    groupBtn: document.getElementById("group-btn"),
    deleteBtn: document.getElementById("delete-btn"),
    exportBtn: document.getElementById("export-btn"),
    zoomInBtn: document.getElementById("zoom-in-btn"),
    zoomOutBtn: document.getElementById("zoom-out-btn"),
};

const state = {
    project: createProject(),
    selection: [],
    playhead: 0,
    zoom: 90,
    isPlaying: false,
    lastFrameTime: 0,
    activeTab: "media",
    clientId: uid("client"),
};

const TEXT_PRESETS = {
    title: {
        name: "Title",
        text: "ข้อความหัวเรื่อง",
        duration: 3.8,
        style: { x: 50, y: 18, fontSize: 72, color: "#ffffff", strokeColor: "#000000", strokeWidth: 4, shadow: true, opacity: 1, animation: "pop" },
    },
    subtitle: {
        name: "Subtitle",
        text: "คำบรรยายแบบอ่านง่าย",
        duration: 3.2,
        style: { x: 50, y: 78, fontSize: 52, color: "#ffffff", strokeColor: "#000000", strokeWidth: 4, shadow: true, opacity: 1, animation: "fade" },
    },
    highlight: {
        name: "Highlight",
        text: "ข้อความเด่น",
        duration: 2.8,
        style: { x: 50, y: 32, fontSize: 64, color: "#fde047", strokeColor: "#000000", strokeWidth: 4, shadow: true, opacity: 1, animation: "bounce" },
    },
};

const app = {
    state,
    refs,
    projectDuration() {
        return state.project.tracks.reduce((max, track) => {
            const trackEnd = track.clips.reduce(
                (end, clip) => Math.max(end, Number(clip.start || 0) + Number(clip.duration || 0)),
                0,
            );
            return Math.max(max, trackEnd);
        }, 0);
    },
    formatTime(seconds) {
        const safe = Math.max(0, Number(seconds || 0));
        const minutes = Math.floor(safe / 60);
        const secs = Math.floor(safe % 60);
        const frames = Math.floor((safe % 1) * 100);
        return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(frames).padStart(2, "0")}`;
    },
    setActiveTab(tab) {
        state.activeTab = tab;
        refs.railTabs.forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
        refs.sidebarViews.forEach((view) => view.classList.toggle("active", view.dataset.view === tab));
    },
    findTrack(trackId) {
        return state.project.tracks.find((track) => track.id === trackId);
    },
    findTrackIndex(trackId) {
        return state.project.tracks.findIndex((track) => track.id === trackId);
    },
    findClip(clipId) {
        for (const track of state.project.tracks) {
            const clip = track.clips.find((item) => item.id === clipId);
            if (clip) {
                return { track, clip };
            }
        }
        return null;
    },
    dragGroup(clipId) {
        const found = app.findClip(clipId);
        if (!found) {
            return [];
        }
        if (!found.clip.groupId) {
            return [clipId];
        }
        const ids = [];
        state.project.tracks.forEach((track) => {
            track.clips.forEach((clip) => {
                if (clip.groupId === found.clip.groupId) {
                    ids.push(clip.id);
                }
            });
        });
        return ids;
    },
    status(message) {
        refs.editorStatus.textContent = message;
    },
    assetById(assetId) {
        return state.project.assets.find((asset) => asset.id === assetId);
    },
    trackOrder(kind) {
        return state.project.tracks.filter((track) => track.kind === kind);
    },
    defaultTrackForKind(kind) {
        return state.project.tracks.find((track) => track.kind === kind && !track.locked) || state.project.tracks.find((track) => track.kind === kind);
    },
    preferredTrackForAsset(assetKind) {
        if (assetKind === "audio") {
            return app.defaultTrackForKind("audio");
        }
        return app.defaultTrackForKind("video");
    },
    resolveTrackForClipType(clipType, desiredTrackId = null) {
        const desiredTrack = desiredTrackId ? app.findTrack(desiredTrackId) : null;
        const compatibility = {
            video: ["video", "image"],
            audio: ["audio"],
            subtitle: ["subtitle"],
            effect: ["effect", "subtitle"],
        };

        if (desiredTrack && !desiredTrack.locked && compatibility[desiredTrack.kind]?.includes(clipType)) {
            return desiredTrack;
        }

        if (clipType === "audio") {
            return app.defaultTrackForKind("audio");
        }
        if (clipType === "subtitle") {
            return app.defaultTrackForKind("subtitle");
        }
        if (clipType === "effect") {
            return app.defaultTrackForKind("effect");
        }
        return app.defaultTrackForKind("video");
    },
    clearSelection() {
        state.selection = [];
        app.render();
    },
    selectClip(clipId, additive = false) {
        if (additive) {
            if (state.selection.includes(clipId)) {
                state.selection = state.selection.filter((id) => id !== clipId);
            } else {
                state.selection = [...state.selection, clipId];
            }
        } else {
            state.selection = [clipId];
        }
        app.render();
    },
    seekTo(time) {
        const duration = Math.max(app.projectDuration(), 1);
        state.playhead = Math.max(0, Math.min(duration, Number(time || 0)));
        app.render(false);
    },
    addTrack(kind) {
        const count = state.project.tracks.filter((track) => track.kind === kind).length + 1;
        const nameMap = { video: "Video", audio: "Audio", subtitle: "Subtitle", effect: "Text" };
        state.project.tracks.push(createTrack(kind, count === 1 ? nameMap[kind] || "Track" : `${nameMap[kind] || "Track"} ${count}`));
        app.render();
    },
    createAssetClip(asset, start = state.playhead) {
        const defaults = {
            video: { duration: 8, style: { opacity: 1, volume: 1 } },
            image: { duration: 5, style: { opacity: 1 } },
            audio: { duration: 8, style: { volume: 1 } },
        };
        const preset = defaults[asset.kind] || defaults.video;
        return {
            id: uid("clip"),
            assetId: asset.id,
            sourcePath: asset.path,
            sourceUrl: asset.url,
            name: asset.name,
            start: Number(start || 0),
            duration: preset.duration,
            sourceIn: 0,
            type: asset.kind,
            groupId: null,
            hidden: false,
            style: structuredClone(preset.style),
        };
    },
    addAssetClip(assetId, trackId, start) {
        const asset = app.assetById(assetId);
        if (!asset) {
            return;
        }
        const track = app.resolveTrackForClipType(asset.kind, trackId);
        if (!track || track.locked) {
            return;
        }
        const clip = app.createAssetClip(asset, start);
        track.clips.push(clip);
        state.selection = [clip.id];
        app.status(`เพิ่ม ${asset.name} ลง timeline แล้ว`);
        app.render();
    },
    insertAssetAutomatically(asset) {
        const track = app.preferredTrackForAsset(asset.kind);
        if (!track || track.locked) {
            return null;
        }
        const trackEnd = track.clips.reduce(
            (end, clip) => Math.max(end, Number(clip.start || 0) + Number(clip.duration || 0)),
            0,
        );
        const clip = app.createAssetClip(asset, Math.max(state.playhead, trackEnd));
        track.clips.push(clip);
        state.selection = [clip.id];
        return clip;
    },
    addTextClip(presetName = "title", trackId = null, start = state.playhead) {
        const preset = TEXT_PRESETS[presetName] || TEXT_PRESETS.title;
        const track = app.resolveTrackForClipType("effect", trackId);
        if (!track) {
            return;
        }
        const clip = {
            id: uid("text"),
            type: "effect",
            name: preset.name,
            text: preset.text,
            start: Number(start || 0),
            duration: preset.duration,
            groupId: null,
            hidden: false,
            style: structuredClone(preset.style),
        };
        track.clips.push(clip);
        state.selection = [clip.id];
        app.status(`เพิ่ม ${preset.name} แล้ว`);
        app.render();
    },
    moveClipsToTrack(clipIds, targetTrackId) {
        clipIds.forEach((clipId) => {
            const found = app.findClip(clipId);
            if (!found) {
                return;
            }
            const nextTrack = app.resolveTrackForClipType(found.clip.type, targetTrackId);
            if (!nextTrack || nextTrack.id === found.track.id || nextTrack.locked) {
                return;
            }
            found.track.clips = found.track.clips.filter((clip) => clip.id !== clipId);
            nextTrack.clips.push(found.clip);
        });
    },
    splitSelectedClip() {
        const selectedId = state.selection[0];
        const found = app.findClip(selectedId);
        if (!found || found.track.locked) {
            return;
        }
        const clip = found.clip;
        const splitAt = state.playhead;
        const clipStart = Number(clip.start);
        const clipEnd = clipStart + Number(clip.duration);
        if (splitAt <= clipStart + 0.1 || splitAt >= clipEnd - 0.1) {
            app.status("เลื่อนเส้นเวลาให้อยู่กลางคลิปก่อน");
            return;
        }
        const firstDuration = splitAt - clipStart;
        const secondDuration = clipEnd - splitAt;
        const newClip = structuredClone(clip);
        newClip.id = uid("clip");
        newClip.start = splitAt;
        newClip.duration = secondDuration;
        newClip.sourceIn = Number(clip.sourceIn || 0) + firstDuration;
        clip.duration = firstDuration;
        found.track.clips.push(newClip);
        state.selection = [newClip.id];
        app.render();
    },
    duplicateSelection() {
        const copies = [];
        state.selection.forEach((clipId) => {
            const found = app.findClip(clipId);
            if (!found || found.track.locked) {
                return;
            }
            const duplicate = structuredClone(found.clip);
            duplicate.id = uid("clip");
            duplicate.start = Number(found.clip.start) + Number(found.clip.duration) + 0.15;
            duplicate.name = found.clip.name;
            found.track.clips.push(duplicate);
            copies.push(duplicate.id);
        });
        if (copies.length) {
            state.selection = copies;
            app.render();
        }
    },
    deleteSelection() {
        if (!state.selection.length) {
            return;
        }
        state.project.tracks.forEach((track) => {
            if (track.locked) {
                return;
            }
            track.clips = track.clips.filter((clip) => !state.selection.includes(clip.id));
        });
        state.selection = [];
        app.render();
    },
    groupSelection() {
        if (state.selection.length < 2) {
            app.status("เลือกอย่างน้อย 2 คลิปก่อน");
            return;
        }
        const groupId = uid("group");
        state.selection.forEach((clipId) => {
            const found = app.findClip(clipId);
            if (found) {
                found.clip.groupId = groupId;
            }
        });
        app.render();
    },
    applyInspector() {
        const found = app.findClip(state.selection[0]);
        if (!found) {
            return;
        }
        const clip = found.clip;
        clip.name = refs.clipNameInput.value || clip.name;
        clip.start = Math.max(0, Number(refs.clipStartInput.value || clip.start));
        clip.duration = Math.max(0.2, Number(refs.clipDurationInput.value || clip.duration));

        if (clip.type === "effect" || clip.type === "subtitle") {
            clip.text = refs.clipTextInput.value || clip.text;
            clip.style = {
                ...(clip.style || {}),
                x: Number(refs.clipXInput.value || 50),
                y: Number(refs.clipYInput.value || 50),
                fontSize: Number(refs.clipFontSizeInput.value || 54),
                opacity: Number(refs.clipOpacityInput.value || 1),
                color: refs.clipColorInput.value || "#ffffff",
                strokeColor: refs.clipStrokeColorInput.value || "#000000",
                animation: refs.clipAnimationInput.value || "none",
            };
        }
        app.render();
    },
    async saveCurrentProject() {
        const projectName = window.prompt("Project name", state.project.name);
        if (projectName) {
            state.project.name = projectName;
        }
        const result = await saveProject(state.project);
        app.status(`บันทึก ${result.projectId} แล้ว`);
        app.render();
    },
    async loadExistingProject() {
        const result = await listProjects();
        if (!result.projects?.length) {
            app.status("ยังไม่มีโปรเจคที่บันทึกไว้");
            return;
        }
        const projectId = window.prompt(
            `เลือก Project ID\n${result.projects.map((item) => `${item.id} - ${item.name}`).join("\n")}`,
            result.projects[0].id,
        );
        if (!projectId) {
            return;
        }
        const payload = await loadProject(projectId);
        state.project = payload.project;
        state.selection = [];
        state.playhead = 0;
        app.status(`โหลด ${projectId} แล้ว`);
        app.render();
    },
    async runAutoSubtitle() {
        const selectedId = state.selection[0];
        const found = selectedId ? app.findClip(selectedId) : null;
        const targetClip = found?.clip?.type === "video"
            ? found.clip
            : state.project.tracks.flatMap((track) => track.clips).find((clip) => clip.type === "video");

        if (!targetClip) {
            app.status("ต้องมีคลิปวิดีโอก่อน");
            return;
        }

        app.status("กำลังสร้าง subtitle...");
        const payload = await requestAutoSubtitle(targetClip.sourcePath);
        const subtitleTrack = app.defaultTrackForKind("subtitle");
        subtitleTrack.clips = subtitleTrack.clips.concat(
            payload.clips.map((clip) => ({
                ...clip,
                start: Number(targetClip.start) + Number(clip.start || 0),
                type: "subtitle",
            })),
        );
        app.setActiveTab("subtitle");
        app.status(`เพิ่มซับ ${payload.clips.length} ชิ้นแล้ว`);
        app.render();
    },
    async exportCurrentProject() {
        app.status("กำลัง export โปรเจค...");
        const payload = await exportProject(state.project);
        app.status("Export เสร็จแล้ว");
        window.open(payload.outputUrl, "_blank");
    },
    render(updateTimeline = true) {
        refs.projectNameView.textContent = state.project.name;
        refs.assetCount.textContent = `${state.project.assets.length} files`;
        refs.projectDurationView.textContent = `${app.projectDuration().toFixed(1)}s`;
        refs.timelineZoomView.textContent = `${state.zoom} px/s`;
        refs.timecodeView.textContent = app.formatTime(state.playhead);
        refs.playheadSlider.max = String(Math.max(100, Math.ceil(app.projectDuration() * 100)));
        refs.playheadSlider.value = String(Math.round(state.playhead * 100));
        if (updateTimeline) {
            renderAssets();
        }
        if (updateTimeline) {
            renderTimeline(app);
        } else {
            refs.playheadLine.style.left = `${state.playhead * state.zoom}px`;
        }
        if (updateTimeline) {
            renderInspector();
        }
        updatePreview(app);
    },
};

function renderAssets() {
    refs.assetList.innerHTML = "";
    state.project.assets.forEach((asset) => {
        const node = document.createElement("div");
        node.className = "asset-card";
        node.draggable = true;
        const thumbLabel = asset.kind === "video" ? "VIDEO" : asset.kind === "audio" ? "AUDIO" : "IMAGE";
        node.innerHTML = `
            <div class="asset-thumb">${thumbLabel}</div>
            <div class="asset-name">${asset.name}</div>
            <div class="asset-meta">${(asset.size / 1024 / 1024).toFixed(2)} MB</div>
        `;
        node.addEventListener("dragstart", (event) => {
            event.dataTransfer.setData("text/asset-id", asset.id);
        });
        node.addEventListener("dblclick", () => {
            app.addAssetClip(asset.id, null, state.playhead);
        });
        refs.assetList.appendChild(node);
    });
}

function renderInspector() {
    const found = app.findClip(state.selection[0]);
    if (!found) {
        refs.selectionKind.textContent = "No Selection";
        refs.inspectorEmpty.classList.remove("hidden");
        refs.inspectorForm.classList.add("hidden");
        return;
    }

    const clip = found.clip;
    const style = clip.style || {};
    const isTextClip = clip.type === "effect" || clip.type === "subtitle";
    refs.selectionKind.textContent = clip.type === "image" ? "Image" : clip.type.charAt(0).toUpperCase() + clip.type.slice(1);
    refs.inspectorEmpty.classList.add("hidden");
    refs.inspectorForm.classList.remove("hidden");
    refs.textOnlyFields.forEach((node) => node.classList.toggle("hidden", !isTextClip));

    refs.clipNameInput.value = clip.name || "";
    refs.clipTextInput.value = clip.text || "";
    refs.clipStartInput.value = Number(clip.start || 0).toFixed(2);
    refs.clipDurationInput.value = Number(clip.duration || 1).toFixed(2);
    refs.clipXInput.value = Number(style.x ?? 50);
    refs.clipYInput.value = Number(style.y ?? 50);
    refs.clipFontSizeInput.value = Number(style.fontSize ?? 54);
    refs.clipOpacityInput.value = Number(style.opacity ?? 1);
    refs.clipColorInput.value = style.color || "#ffffff";
    refs.clipStrokeColorInput.value = style.strokeColor || "#000000";
    refs.clipAnimationInput.value = style.animation || "none";
}

function updatePlayButton() {
    refs.playPauseBtn.textContent = state.isPlaying ? "❚❚" : "▶";
}

function tick(timestamp) {
    if (!state.isPlaying) {
        return;
    }
    if (!state.lastFrameTime) {
        state.lastFrameTime = timestamp;
    }
    const delta = (timestamp - state.lastFrameTime) / 1000;
    state.lastFrameTime = timestamp;
    app.seekTo(state.playhead + delta);
    if (state.playhead >= app.projectDuration()) {
        state.isPlaying = false;
        updatePlayButton();
        return;
    }
    requestAnimationFrame(tick);
}

function togglePlay() {
    state.isPlaying = !state.isPlaying;
    state.lastFrameTime = 0;
    updatePlayButton();
    if (state.isPlaying) {
        requestAnimationFrame(tick);
    } else {
        refs.previewVideo.pause();
    }
}

async function handleUpload(files) {
    if (!files.length) {
        return;
    }
    app.status(`กำลังอัปโหลด ${files.length} ไฟล์...`);
    for (const file of files) {
        const asset = await uploadMedia(file);
        if (!state.project.assets.some((item) => item.id === asset.id)) {
            state.project.assets.push(asset);
        }
        app.insertAssetAutomatically(asset);
    }
    app.status("อัปโหลดเสร็จแล้ว");
    app.render();
}

function bindRealtime() {
    connectRealtime((eventName, payload) => {
        if (eventName === "asset_uploaded" && payload.asset) {
            const exists = state.project.assets.some((asset) => asset.id === payload.asset.id);
            if (!exists) {
                state.project.assets.push(payload.asset);
                app.status(`Imported ${payload.asset.name}`);
                app.render();
            }
        }
        if (eventName === "project_saved" && payload.project?.id === state.project.id) {
            state.project = payload.project;
            app.status("Project synced");
            app.render();
        }
    });
}

function bindEvents() {
    refs.railTabs.forEach((button) => {
        button.addEventListener("click", () => app.setActiveTab(button.dataset.tab));
    });

    refs.mediaUploadInput.addEventListener("change", async (event) => {
        const files = Array.from(event.target.files || []);
        refs.mediaUploadInput.value = "";
        try {
            await handleUpload(files);
        } catch (error) {
            app.status(error.message);
        }
    });

    refs.presetCards.forEach((card) => {
        card.addEventListener("dragstart", (event) => {
            event.dataTransfer.setData("text/text-preset", card.dataset.textPreset);
        });
        card.addEventListener("dblclick", () => {
            app.addTextClip(card.dataset.textPreset);
        });
    });

    refs.addTextBtn.addEventListener("click", () => app.addTextClip("title"));
    refs.splitBtn.addEventListener("click", () => app.splitSelectedClip());
    refs.duplicateBtn.addEventListener("click", () => app.duplicateSelection());
    refs.groupBtn.addEventListener("click", () => app.groupSelection());
    refs.deleteBtn.addEventListener("click", () => app.deleteSelection());
    refs.applyInspectorBtn.addEventListener("click", () => app.applyInspector());
    refs.autoSubtitleBtn.addEventListener("click", async () => {
        try {
            await app.runAutoSubtitle();
        } catch (error) {
            app.status(error.message);
        }
    });
    refs.exportBtn.addEventListener("click", async () => {
        try {
            await app.exportCurrentProject();
        } catch (error) {
            app.status(error.message);
        }
    });
    refs.saveProjectBtn.addEventListener("click", async () => {
        try {
            await app.saveCurrentProject();
        } catch (error) {
            app.status(error.message);
        }
    });
    refs.loadProjectBtn.addEventListener("click", async () => {
        try {
            await app.loadExistingProject();
        } catch (error) {
            app.status(error.message);
        }
    });
    refs.newProjectBtn.addEventListener("click", () => {
        state.project = createProject();
        state.selection = [];
        state.playhead = 0;
        state.activeTab = "media";
        app.setActiveTab("media");
        app.status("สร้างโปรเจคใหม่แล้ว");
        app.render();
    });
    refs.zoomInBtn.addEventListener("click", () => {
        state.zoom = Math.min(220, state.zoom + 15);
        app.render();
    });
    refs.zoomOutBtn.addEventListener("click", () => {
        state.zoom = Math.max(35, state.zoom - 15);
        app.render();
    });
    refs.playPauseBtn.addEventListener("click", () => togglePlay());
    refs.rewindBtn.addEventListener("click", () => app.seekTo(state.playhead - 1));
    refs.forwardBtn.addEventListener("click", () => app.seekTo(state.playhead + 1));
    refs.playheadSlider.addEventListener("input", (event) => app.seekTo(Number(event.target.value) / 100));
    document.querySelectorAll("[data-add-track]").forEach((button) => {
        button.addEventListener("click", () => app.addTrack(button.dataset.addTrack));
    });

    refs.timelineScroll.addEventListener("scroll", () => {
        refs.trackHeaderList.scrollTop = Math.max(0, refs.timelineScroll.scrollTop - refs.timelineRuler.offsetHeight);
    });

    document.addEventListener("keydown", (event) => {
        const tag = document.activeElement?.tagName;
        const isTyping = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";

        if (event.code === "Space" && !isTyping) {
            event.preventDefault();
            togglePlay();
            return;
        }
        if (isTyping) {
            return;
        }
        if (event.key === "Delete") {
            app.deleteSelection();
        } else if (event.key.toLowerCase() === "d" && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            app.duplicateSelection();
        } else if (event.key.toLowerCase() === "s" && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            app.saveCurrentProject().catch((error) => app.status(error.message));
        }
    });
}

bindEvents();
bindRealtime();
app.setActiveTab("media");
updatePlayButton();
app.render();
