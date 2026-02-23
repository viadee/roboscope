/**
 * Simple markdown-to-HTML renderer.
 * Supports: headers, bold, italic, code blocks, inline code, lists, paragraphs.
 * HTML is escaped first to prevent XSS.
 */
export function renderMarkdown(md: string): string {
  // Escape HTML
  let html = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // Code blocks
  html = html.replace(/```[\w]*\n([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  // Headers
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  // Bold
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // Italic
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // Unordered lists
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
  // Collapse adjacent </ul><ul>
  html = html.replace(/<\/ul>\s*<ul>/g, '')
  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
  // Paragraphs — double newlines
  html = html.replace(/\n\n/g, '</p><p>')
  html = '<p>' + html + '</p>'
  // Clean up empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, '')
  return html
}
