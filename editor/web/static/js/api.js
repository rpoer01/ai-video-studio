async function parseResponse(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(data.error || `Request failed with status ${response.status}`);
    }
    return data;
}

export async function uploadMedia(file) {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch("/api/media/upload", {
        method: "POST",
        body: formData,
    });
    return parseResponse(response);
}

export async function saveProject(project) {
    const response = await fetch("/api/project/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project }),
    });
    return parseResponse(response);
}

export async function loadProject(projectId) {
    const response = await fetch(`/api/project/${encodeURIComponent(projectId)}`);
    return parseResponse(response);
}

export async function listProjects() {
    const response = await fetch("/api/project/list");
    return parseResponse(response);
}

export async function requestAutoSubtitle(mediaPath) {
    const response = await fetch("/api/auto-subtitle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            mediaPath,
            languageCode: "th",
            maxWords: 3,
        }),
    });
    return parseResponse(response);
}

export async function exportProject(project) {
    const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project }),
    });
    return parseResponse(response);
}
