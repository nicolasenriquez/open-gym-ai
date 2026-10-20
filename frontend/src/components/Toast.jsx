import { useLayoutEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useUI } from '../store/useUI.js'
import Icon from './Icon.jsx'

// The one toast. Mostly text; with an action (the Undo after a set is removed) it carries a button
// at its end, stays longer and holds still while a finger or the mouse rests on it.
export default function Toast() {
  const msg = useUI(s => s.toastMsg)
  const action = useUI(s => s.toastAction)
  const sheetId = useUI(s => s.sheets.at(-1)?.id)
  const [host, setHost] = useState(null)
  // Native modal dialogs make outside controls inert, including the toast's Undo action.
  useLayoutEffect(() => {
    setHost(sheetId ? document.getElementById(`sheet-${sheetId}`) : null)
  }, [sheetId])
  const { pauseToast, resumeToast, runToastAction } = useUI.getState()
  const live = !!(msg && action)
  const content = <div id="toast" role="status" className={(msg ? 'show' : '') + (live ? ' has-action' : '')}
    onPointerEnter={live ? pauseToast : undefined} onPointerDown={live ? pauseToast : undefined}
    onPointerLeave={live ? resumeToast : undefined} onPointerCancel={live ? resumeToast : undefined}
    onPointerUp={live ? (e => { if (e.pointerType !== 'mouse') resumeToast() }) : undefined}>
    <span className="toast-msg">{msg}</span>
    {live && <button type="button" className="toast-act" key={action.id} onClick={runToastAction}>
      <Icon name="undo" />{action.label}
    </button>}
  </div>
  return host ? createPortal(content, host) : content
}
