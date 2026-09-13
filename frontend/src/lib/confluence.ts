/**
 * People paste the page they're looking at. Pull the site and the space key out
 * of it so they don't have to dissect the URL by hand.
 *   https://x.atlassian.net/wiki/spaces/~7120…/pages/393218/Some+Doc
 *     -> { site: "https://x.atlassian.net/wiki", spaceKey: "~7120…" }
 */
export function parseConfluenceUrl(raw: string): { site: string; spaceKey?: string } {
  const v = raw.trim().replace(/\/+$/, '')
  if (!/^https?:\/\//i.test(v)) return { site: v }
  const site = v.replace(/(\/wiki)\/.*$/i, '$1')
  const m = v.match(/\/wiki\/spaces\/([^/?#]+)/i)
  return { site, spaceKey: m ? decodeURIComponent(m[1]) : undefined }
}
