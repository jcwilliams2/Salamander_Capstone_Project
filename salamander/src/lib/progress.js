export function describeProgress(percent, page, pageCount) {
    const shown = percent ?? 0
    if (pageCount && (page != null || percent == null)) return `${shown}% · page ${page ?? 0} of ${pageCount}`
    return `${shown}%`
}