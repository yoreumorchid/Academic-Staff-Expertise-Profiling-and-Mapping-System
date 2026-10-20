import ReactMarkdown from "react-markdown";

interface MarkdownSummaryProps {
  children: string;
  fallback?: string;
}

export function MarkdownSummary({ children, fallback = "No summary is available." }: MarkdownSummaryProps) {
  const content = children.trim() || fallback;

  return (
    <div className="text-small text-text-secondary">
      <ReactMarkdown
        skipHtml
        disallowedElements={["img"]}
        unwrapDisallowed
        components={{
          h1: ({ children: heading }) => <h4 className="mt-4 first:mt-0 font-announce text-text-primary">{heading}</h4>,
          h2: ({ children: heading }) => <h4 className="mt-4 first:mt-0 font-announce text-text-primary">{heading}</h4>,
          h3: ({ children: heading }) => <h4 className="mt-4 first:mt-0 font-announce text-text-primary">{heading}</h4>,
          h4: ({ children: heading }) => <h4 className="mt-4 first:mt-0 font-announce text-text-primary">{heading}</h4>,
          h5: ({ children: heading }) => <h4 className="mt-4 first:mt-0 font-signature text-text-primary">{heading}</h4>,
          h6: ({ children: heading }) => <h4 className="mt-4 first:mt-0 font-signature text-text-primary">{heading}</h4>,
          p: ({ children: paragraph }) => <p className="mt-2 first:mt-0 leading-relaxed">{paragraph}</p>,
          ul: ({ children: items }) => <ul className="mt-2 list-disc space-y-1 pl-5">{items}</ul>,
          ol: ({ children: items }) => <ol className="mt-2 list-decimal space-y-1 pl-5">{items}</ol>,
          strong: ({ children: text }) => <strong className="font-signature text-text-primary">{text}</strong>,
          blockquote: ({ children: quote }) => (
            <blockquote className="mt-2 border-l-2 border-brand-indigo pl-3 text-text-tertiary">{quote}</blockquote>
          ),
          code: ({ children: code }) => (
            <code className="rounded-micro bg-bg-secondary px-1 py-0.5 font-mono text-caption text-text-primary">{code}</code>
          ),
          a: ({ href, children: label }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="text-brand-violet underline underline-offset-2 hover:text-brand-hover"
            >
              {label}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
