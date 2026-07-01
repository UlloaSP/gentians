export const chartTw = {
  page: [
    'min-h-screen', 'bg-neutral-50', 'px-6', 'py-6', 'text-neutral-950',
    'dark:bg-neutral-950', 'dark:text-neutral-50',
  ].join(' '),
  shell: ['mx-auto', 'flex', 'w-full', 'max-w-[1800px]', 'flex-col', 'gap-5'].join(' '),
  sectionGrid: ['grid', 'grid-cols-1', 'gap-4', 'xl:grid-cols-12'].join(' '),
  chartSm: ['h-[260px]', 'w-full', 'min-w-0'].join(' '),
  chartMd: ['h-[340px]', 'w-full', 'min-w-0'].join(' '),
  chartLg: ['h-[420px]', 'w-full', 'min-w-0'].join(' '),
  chartXl: ['h-[520px]', 'w-full', 'min-w-0'].join(' '),
  controlsBar: [
    'flex', 'flex-wrap', 'items-center', 'gap-2', 'rounded-xl', 'border',
    'border-neutral-200', 'bg-white', 'p-3', 'shadow-sm',
    'dark:border-neutral-800', 'dark:bg-neutral-900',
  ].join(' '),
  controlLabel: ['text-xs', 'font-medium', 'text-neutral-500', 'dark:text-neutral-400'].join(' '),
  select: [
    'h-9', 'rounded-lg', 'border', 'border-neutral-200', 'bg-white', 'px-3',
    'text-sm', 'text-neutral-900', 'outline-none', 'transition',
    'hover:border-neutral-300', 'focus:border-blue-500', 'focus:ring-2',
    'focus:ring-blue-500/20', 'dark:border-neutral-700', 'dark:bg-neutral-950',
    'dark:text-neutral-100', 'dark:hover:border-neutral-600',
  ].join(' '),
  button: [
    'inline-flex', 'h-9', 'items-center', 'justify-center', 'rounded-lg',
    'border', 'border-neutral-200', 'bg-white', 'px-3', 'text-sm',
    'font-medium', 'text-neutral-700', 'transition', 'hover:bg-neutral-50',
    'focus:outline-none', 'focus:ring-2', 'focus:ring-blue-500/20',
    'dark:border-neutral-700', 'dark:bg-neutral-900', 'dark:text-neutral-200',
    'dark:hover:bg-neutral-800',
  ].join(' '),
  buttonActive: [
    'inline-flex', 'h-9', 'items-center', 'justify-center', 'rounded-lg',
    'border', 'border-blue-600', 'bg-blue-600', 'px-3', 'text-sm',
    'font-medium', 'text-white', 'shadow-sm', 'transition', 'hover:bg-blue-700',
    'focus:outline-none', 'focus:ring-2', 'focus:ring-blue-500/30',
  ].join(' '),
  tableWrap: [
    'overflow-hidden', 'rounded-lg', 'border', 'border-neutral-200', 'bg-white',
    'dark:border-neutral-800', 'dark:bg-neutral-900',
  ].join(' '),
  tableScroller: ['max-h-[520px]', 'overflow-auto'].join(' '),
  table: ['min-w-full', 'border-collapse', 'text-left', 'text-sm'].join(' '),
  th: [
    'sticky', 'top-0', 'z-10', 'border-b', 'border-neutral-200', 'bg-neutral-50',
    'px-3', 'py-2', 'text-xs', 'font-semibold', 'uppercase', 'tracking-wide',
    'text-neutral-500', 'dark:border-neutral-800', 'dark:bg-neutral-950',
    'dark:text-neutral-400',
  ].join(' '),
  td: [
    'border-b', 'border-neutral-100', 'px-3', 'py-2', 'text-neutral-700',
    'dark:border-neutral-800', 'dark:text-neutral-200',
  ].join(' '),
  metricLabel: [
    'text-xs', 'font-medium', 'uppercase', 'tracking-wide', 'text-neutral-500',
    'dark:text-neutral-400',
  ].join(' '),
  metricValue: [
    'mt-2', 'block', 'break-words', 'text-2xl', 'font-semibold', 'tracking-tight', 'text-neutral-950',
    'dark:text-neutral-50',
  ].join(' '),
  metricHint: ['mt-1', 'text-xs', 'leading-5', 'text-neutral-500', 'dark:text-neutral-400'].join(' '),
  note: [
    'rounded-lg', 'border', 'border-blue-200', 'bg-blue-50', 'px-3', 'py-2',
    'text-xs', 'leading-5', 'text-blue-900', 'dark:border-blue-900/60',
    'dark:bg-blue-950/40', 'dark:text-blue-200',
  ].join(' '),
}
