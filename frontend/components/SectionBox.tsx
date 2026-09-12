import CopyButton from "./CopyButton";

export default function SectionBox({
  title,
  copyText,
  children,
}: {
  title: string;
  copyText: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white dark:border-neutral-700 dark:bg-neutral-900">
      <div className="flex items-center justify-between border-b border-neutral-200 px-3 py-2 dark:border-neutral-700">
        <h3 className="text-sm font-semibold text-neutral-800 dark:text-neutral-100">{title}</h3>
        <CopyButton text={copyText} />
      </div>
      <div className="px-3 py-2 text-sm text-neutral-700 dark:text-neutral-200">{children}</div>
    </div>
  );
}
