export const PREVIEW_REFERENCE_WIDTH = 320;

export function outputWidth(project) {
    return Math.max(1, Number(project?.resolution?.width || 1080));
}

export function previewScaleForCanvas(canvasWidth) {
    return Math.max(1, Number(canvasWidth || PREVIEW_REFERENCE_WIDTH)) / PREVIEW_REFERENCE_WIDTH;
}

export function previewFontSizeForStyle(style, project) {
    const rawSize = Number(style?.fontSize ?? 24);
    if (style?.fontSizeMode === "preview") {
        return rawSize;
    }
    return rawSize * (PREVIEW_REFERENCE_WIDTH / outputWidth(project));
}

export function renderFontSizeForPreviewSize(previewSize, project) {
    return Math.max(1, Math.round(Number(previewSize || 24) * (outputWidth(project) / PREVIEW_REFERENCE_WIDTH)));
}

export function previewStrokeWidthForStyle(style, project) {
    const fontSize = previewFontSizeForStyle(style, project);
    const rawStroke = Number(style?.strokeWidth ?? Math.max(1, fontSize * 0.06));
    if (style?.fontSizeMode === "preview") {
        return rawStroke;
    }
    return rawStroke * (PREVIEW_REFERENCE_WIDTH / outputWidth(project));
}
