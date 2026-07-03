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
  floatingSelect: ['fixed', 'right-4', 'top-4', 'z-50'].join(' '),
  floatingButton: [
    'flex', 'h-11', 'w-11', 'flex-col', 'items-center', 'justify-center', 'gap-1.5',
    'rounded', 'border', 'border-neutral-200/80', 'bg-white/95', 'shadow-lg',
    'backdrop-blur', 'transition', 'hover:border-neutral-300', 'hover:bg-white',
    'focus:outline-none', 'focus:ring-2', 'focus:ring-blue-500/30',
    'dark:border-neutral-700/80', 'dark:bg-neutral-950/95', 'dark:hover:border-neutral-600',
    '[&>span]:h-0.5', '[&>span]:w-5', '[&>span]:rounded-full',
    '[&>span]:bg-neutral-900', 'dark:[&>span]:bg-neutral-100',
  ].join(' '),
  modalBackdrop: [
    'fixed', 'inset-0', 'z-40', 'flex', 'items-start', 'justify-end',
    'bg-neutral-950/20', 'px-4', 'py-16', 'backdrop-blur-sm',
    'dark:bg-neutral-950/55',
  ].join(' '),
  benchmarkDialog: [
    'w-full', 'max-w-sm', 'rounded', 'border', 'border-neutral-200',
    'bg-white', 'p-4', 'shadow-2xl', 'dark:border-neutral-800', 'dark:bg-neutral-950',
  ].join(' '),
  benchmarkOption: [
    'flex', 'h-10', 'items-center', 'gap-3', 'rounded', 'px-3', 'text-left',
    'text-sm', 'font-medium', 'text-neutral-700', 'transition', 'hover:bg-neutral-100',
    'focus:outline-none', 'focus:ring-2', 'focus:ring-blue-500/25',
    'dark:text-neutral-200', 'dark:hover:bg-neutral-900',
  ].join(' '),
  benchmarkOptionActive: [
    'flex', 'h-10', 'items-center', 'gap-3', 'rounded', 'bg-blue-600',
    'px-3', 'text-left', 'text-sm', 'font-semibold', 'text-white',
    'shadow-sm', 'focus:outline-none', 'focus:ring-2', 'focus:ring-blue-500/30',
  ].join(' '),
  controlLabel: ['text-xs', 'font-medium', 'text-neutral-500', 'dark:text-neutral-400'].join(' '),
  select: [
    'h-9', 'rounded-lg', 'border', 'border-neutral-200', 'bg-white', 'px-3',
    'text-sm', 'text-neutral-900', 'outline-none', 'transition',
    'hover:border-neutral-300', 'focus:border-blue-500', 'focus:ring-2',
    'focus:ring-blue-500/20', 'dark:border-neutral-700', 'dark:bg-neutral-950',
    'dark:text-neutral-100', 'dark:hover:border-neutral-600',
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
