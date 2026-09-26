import { onBeforeUnmount, watch } from 'vue';
import type { Ref, WatchSource } from 'vue';

// A tab strip that scrolls sideways on narrow screens. The edge that hides
// more tabs fades out, and the selected tab is scrolled into view whenever
// the selection or the set of tabs changes. The strip must be positioned so
// each tab's offsetLeft is measured from the strip itself.
const EDGE_PAD = 24;

export function useScrollFade(strip: Ref<HTMLElement | null>, selection: WatchSource<string>): void {
  let observer: ResizeObserver | null = null;

  function updateEdges(): void {
    const element = strip.value;

    if (!element) return;

    const hidden = element.scrollWidth - element.clientWidth;

    element.classList.toggle('fade-start', element.scrollLeft > 1);
    element.classList.toggle('fade-end', element.scrollLeft < hidden - 1);
  }

  function revealSelected(): void {
    const element = strip.value;
    const tab = element?.querySelector<HTMLElement>('[aria-current="page"], [aria-selected="true"]');

    if (!element || !tab) return;

    const start = tab.offsetLeft;
    const end = start + tab.offsetWidth;

    if (start < element.scrollLeft + EDGE_PAD) element.scrollLeft = Math.max(start - EDGE_PAD, 0);
    else if (end > element.scrollLeft + element.clientWidth - EDGE_PAD) element.scrollLeft = end - element.clientWidth + EDGE_PAD;

    updateEdges();
  }

  function detach(element: HTMLElement | null): void {
    element?.removeEventListener('scroll', updateEdges);
    observer?.disconnect();
    observer = null;
  }

  // The strip can appear after mount, for example when a case opens.
  watch(
    strip,
    (element, previous) => {
      detach(previous ?? null);

      if (!element) return;

      element.addEventListener('scroll', updateEdges, { passive: true });
      observer = new ResizeObserver(updateEdges);
      observer.observe(element);
      revealSelected();
    },
    { flush: 'post' },
  );

  watch(selection, revealSelected, { flush: 'post' });

  onBeforeUnmount(() => {
    detach(strip.value);
  });
}
