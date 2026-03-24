import React, { useState, useRef, useLayoutEffect } from 'react';

export default function Tooltip({ children, content, position = 'top' }) {
  const [visible, setVisible] = useState(false);
  const [offset, setOffset]   = useState(0);
  const wrapRef   = useRef(null);
  const bubbleRef = useRef(null);

  if (!content) return <>{children}</>;

  // useLayoutEffect fires synchronously after DOM mutation but before paint —
  // the nudge is applied in the same frame the tooltip appears, so no flash.
  useLayoutEffect(() => {
    if (!visible || !bubbleRef.current) return;

    const bb  = bubbleRef.current.getBoundingClientRect();
    const vw  = window.innerWidth;
    const PAD = 10;

    let dx = 0;
    if (bb.left < PAD)        dx = PAD - bb.left;
    if (bb.right > vw - PAD)  dx = (vw - PAD) - bb.right;

    setOffset(dx);
  }, [visible]);

  const hide = () => { setVisible(false); setOffset(0); };

  const posClass = {
    top:    'bottom-full left-1/2 mb-2',
    bottom: 'top-full left-1/2 mt-2',
    left:   'right-full top-1/2 -translate-y-1/2 mr-2',
    right:  'left-full top-1/2 -translate-y-1/2 ml-2',
  }[position] ?? 'bottom-full left-1/2 mb-2';

  return (
    <div
      ref={wrapRef}
      className="relative inline-flex"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={hide}
    >
      {children}
      {visible && (
        <div
          className={`absolute z-50 ${posClass} pointer-events-none`}
          style={{ transform: `translateX(calc(-50% + ${offset}px))` }}
        >
          <div
            ref={bubbleRef}
            className="bg-slate-800 text-white text-xs rounded-lg px-3 py-2 shadow-lg leading-relaxed"
            style={{ width: '260px', whiteSpace: 'normal', wordBreak: 'normal', overflowWrap: 'break-word' }}
          >
            {content}
          </div>
        </div>
      )}
    </div>
  );
}
