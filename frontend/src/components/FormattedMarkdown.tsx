"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface FormattedMarkdownProps {
  content: string;
}

export function FormattedMarkdown({ content }: FormattedMarkdownProps) {
  return (
    <div className="formatted-markdown space-y-3 text-xs sm:text-sm text-slate-800 leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-base sm:text-lg font-extrabold text-[#0a2852] border-b border-slate-200 pb-2 mb-3 mt-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-600 inline-block" />
              <span>{children}</span>
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-sm sm:text-base font-bold text-[#0a2852] mt-4 mb-2 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-sky-500 inline-block" />
              <span>{children}</span>
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-blue-900 mt-3 mb-1.5 flex items-center gap-1.5">
              <span>{children}</span>
            </h3>
          ),
          p: ({ children }) => (
            <p className="leading-relaxed text-slate-700 mb-2.5 last:mb-0">
              {children}
            </p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 space-y-1.5 my-2.5 text-slate-700">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 space-y-1.5 my-2.5 text-slate-700 font-medium">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed pl-1 marker:text-blue-500">{children}</li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-3 pl-3.5 pr-3 py-2.5 rounded-r-2xl border-l-4 border-blue-500 bg-gradient-to-r from-blue-50/70 to-slate-50/50 text-blue-950 font-medium text-xs sm:text-[13px] shadow-xs">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="my-4 overflow-x-auto rounded-2xl border border-slate-200 shadow-sm bg-white">
              <table className="w-full text-left text-xs border-collapse">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-slate-100/80 text-[#0a2852] font-bold border-b border-slate-200 uppercase text-[11px] tracking-wider">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-slate-100 bg-white">
              {children}
            </tbody>
          ),
          tr: ({ children }) => (
            <tr className="hover:bg-blue-50/40 transition-colors">
              {children}
            </tr>
          ),
          th: ({ children }) => (
            <th className="py-2.5 px-3.5 font-bold text-slate-700 select-none">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="py-2.5 px-3.5 text-slate-700 align-top">
              {children}
            </td>
          ),
          code: ({ inline, className, children, ...props }: any) => {
            const isCodeBlock = !inline && Boolean(className);
            if (isCodeBlock) {
              return (
                <div className="my-3 rounded-2xl overflow-hidden bg-slate-900 text-sky-300 p-3.5 font-mono text-xs border border-slate-800 shadow-sm overflow-x-auto">
                  <code className={className} {...props}>
                    {children}
                  </code>
                </div>
              );
            }
            return (
              <code className="font-mono text-[11.5px] px-1.5 py-0.5 rounded-md bg-blue-50 text-blue-700 border border-blue-200/70 font-semibold break-all">
                {children}
              </code>
            );
          },
          strong: ({ children }) => (
            <strong className="font-bold text-[#0a2852]">{children}</strong>
          ),
          hr: () => <hr className="my-4 border-slate-200" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
