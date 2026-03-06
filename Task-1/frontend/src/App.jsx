import { useEffect, useState, useRef } from 'react'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost/api'

const LABELS = [
  { name: 'Personal',  color: '#7c3aed', grad: 'linear-gradient(135deg,#7c3aed,#4f46e5)' },
  { name: 'Work',      color: '#0ea5e9', grad: 'linear-gradient(135deg,#0ea5e9,#6366f1)' },
  { name: 'Health',    color: '#10b981', grad: 'linear-gradient(135deg,#10b981,#0ea5e9)' },
  { name: 'Learning',  color: '#f59e0b', grad: 'linear-gradient(135deg,#f59e0b,#ef4444)' },
  { name: 'Home',      color: '#ec4899', grad: 'linear-gradient(135deg,#ec4899,#8b5cf6)' },
  { name: 'Errands',   color: '#f97316', grad: 'linear-gradient(135deg,#f97316,#eab308)' },
]

const LABEL_MAP = Object.fromEntries(LABELS.map(l => [l.name, l]))
const DAYS_SHORT = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']

function getWeekStart(offset = 0) {
  const d = new Date()
  d.setDate(d.getDate() - d.getDay() + offset * 7)
  d.setHours(0, 0, 0, 0)
  return d
}

function getWeekDays(offset = 0) {
  const start = getWeekStart(offset)
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    return d
  })
}

function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() &&
         a.getMonth()    === b.getMonth()    &&
         a.getDate()     === b.getDate()
}

function taskDate(todo) {
  return todo.scheduled_at ? new Date(todo.scheduled_at) : new Date(todo.created_at)
}

function fmtTime(dateStr) {
  if (!dateStr) return null
  return new Date(dateStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function fmtDateRange(days) {
  const opts = { month: 'short', day: 'numeric' }
  return `${days[0].toLocaleDateString('en', opts)} – ${days[6].toLocaleDateString('en', { ...opts, year: 'numeric' })}`
}

function CustomCheck({ checked, onChange }) {
  return (
    <div
      className={`custom-check ${checked ? 'checked' : ''}`}
      onClick={e => { e.stopPropagation(); onChange() }}
    />
  )
}

function TaskCard({ todo, index, onToggle, onDelete }) {
  const label = LABEL_MAP[todo.label] || LABELS[0]
  const delay = `${(index % 5) * 0.06}s`

  return (
    <div
      className={`task-card ${todo.completed ? 'completed' : ''}`}
      style={{ background: label.grad, animationDelay: delay }}
    >
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:16 }}>
        <span style={{
          background:'rgba(255,255,255,0.2)', borderRadius:16, border:'1px solid rgba(255,255,255,0.1)',
          padding:'6px 12px', fontSize:11.5, color:'#fff', fontWeight:600,
          display:'flex', alignItems:'center', gap:6
        }}>
          <span style={{opacity:0.8}}>⏰</span> {label.name}
        </span>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <CustomCheck checked={todo.completed} onChange={() => onToggle(todo)} />
        </div>
      </div>

      <p className="card-title" style={{
        fontSize:16, fontWeight:700, color:'#fff',
        lineHeight:1.4, wordBreak:'break-word', margin:'0 0 20px',
        flex:1
      }}>
        {todo.title}
      </p>

      <div style={{ display:'flex', justifyContent:'flex-end' }}>
        <button className="delete-btn" onClick={() => onDelete(todo.id)}>✕</button>
      </div>
    </div>
  )
}

function SkeletonCard() {
  return <div className="skeleton" style={{ height:110, marginBottom:10 }} />
}

export default function App() {
  const [todos,       setTodos]       = useState([])
  const [newTitle,    setNewTitle]    = useState('')
  const [newLabel,    setNewLabel]    = useState('Personal')
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState(null)
  const [filter,      setFilter]      = useState('All')
  const [labelFilter, setLabelFilter] = useState(null) 
  const [weekOffset,  setWeekOffset]  = useState(0)
  const [showForm,    setShowForm]    = useState(false)
  const inputRef = useRef(null)

  const weekDays = getWeekDays(weekOffset)
  const today    = new Date()

  const fetchTodos = async () => {
    try {
      const res = await axios.get(`${API_URL}/todos/`)
      setTodos(res.data)
      setError(null)
    } catch { setError('Could not reach the server.') }
    finally  { setLoading(false) }
  }

  const addTodo = async (e) => {
    e.preventDefault()
    if (!newTitle.trim()) return
    const payload = { title: newTitle, label: newLabel }
    try {
      const res = await axios.post(`${API_URL}/todos/`, payload)
      setTodos(prev => [res.data, ...prev])
      setNewTitle(''); setShowForm(false)
    } catch { setError('Failed to add task.') }
  }

  const toggleTodo = async (todo) => {
    try {
      const res = await axios.put(`${API_URL}/todos/${todo.id}/`, { completed: !todo.completed })
      setTodos(prev => prev.map(t => t.id === todo.id ? res.data : t))
    } catch { setError('Failed to update task.') }
  }

  const deleteTodo = async (id) => {
    try {
      await axios.delete(`${API_URL}/todos/${id}/`)
      setTodos(prev => prev.filter(t => t.id !== id))
    } catch { setError('Failed to delete task.') }
  }

  useEffect(() => { fetchTodos() }, [])
  useEffect(() => {
    if (!error) return
    const t = setTimeout(() => setError(null), 4000)
    return () => clearTimeout(t)
  }, [error])

  const filtered = todos.filter(t => {
    const statusOk = filter === 'All'
      ? true
      : filter === 'Active'    ? !t.completed
      : filter === 'Completed' ?  t.completed
      : true
    const labelOk = labelFilter ? t.label === labelFilter : true
    return statusOk && labelOk
  })
  const byDay = weekDays.map(d =>
    filtered
      .filter(t => sameDay(taskDate(t), d))
      .sort((a, b) => taskDate(a) - taskDate(b))
  )
  const outsideWeek = filtered.filter(t =>
    !weekDays.some(d => sameDay(taskDate(t), d))
  )

  const activeCount    = todos.filter(t => !t.completed).length
  const completedCount = todos.filter(t =>  t.completed).length

  function navLabel(item) {
    if (item === 'Active')    { setFilter('Active');    setLabelFilter(null) }
    if (item === 'Completed') { setFilter('Completed'); setLabelFilter(null) }
    if (item === 'Backlog')   { setFilter('All');       setLabelFilter(null) }
  }

  return (
    <div style={{ display:'flex', height:'100vh', overflow:'hidden', background:'#111216' }}>
      <aside style={{
        width:240, background:'#191a21', borderRight:'1px solid #232530',
        display:'flex', flexDirection:'column', flexShrink:0,
        padding:'24px 12px 20px', overflowY:'auto', borderTopRightRadius:20, borderBottomRightRadius:20
      }}>

        {/* Logo */}
        <div style={{ padding:'0 16px 20px', marginBottom:10 }}>
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            <div style={{ fontWeight:700, fontSize:22, color:'#ffffff', letterSpacing:'-0.5px' }}>Tasker</div>
            <div style={{ fontSize:11, color:'#8892b0', fontWeight:600 }}>v1.0</div>
          </div>
        </div>

        {/* Navigation */}
        <div style={{ marginTop:14 }}>
          <div className="sidebar-section-title">Navigation</div>
          {[
            { icon:'▦',  label:'All Tasks',  f:'All',       badge: todos.length || null },
            { icon:'◷',  label:'Active',     f:'Active',    badge: activeCount || null },
            { icon:'◉',  label:'Completed',  f:'Completed', badge: completedCount || null },
          ].map(({ icon, label, f, badge }) => (
            <div
              key={label}
              className={`nav-item ${filter === f && !labelFilter ? 'active' : ''}`}
              onClick={() => { setFilter(f); setLabelFilter(null) }}
            >
              <span style={{ fontSize:13 }}>{icon}</span>
              <span>{label}</span>
              {badge ? <span className="badge">{badge}</span> : null}
            </div>
          ))}
        </div>

        {/* Labels */}
        <div style={{ marginTop:6 }}>
          <div className="sidebar-section-title">Labels</div>
          {LABELS.map(({ name, color }) => {
            const count = todos.filter(t => t.label === name).length
            return (
              <div
                key={name}
                className={`nav-item ${labelFilter === name ? 'active' : ''}`}
                onClick={() => {
                  setLabelFilter(prev => prev === name ? null : name)
                  setFilter('All')
                }}
              >
                <span className="dot" style={{ background: color }} />
                <span>{name}</span>
                {count > 0 && <span className="badge">{count}</span>}
              </div>
            )
          })}
        </div>

        {/* Progress card */}
        <div style={{
          marginTop:'auto', background:'#0f1122', borderRadius:14,
          padding:'14px 16px', border:'1px solid #181c34'
        }}>
          <div style={{ fontSize:10.5, color:'#2d3460', marginBottom:10, fontWeight:700, textTransform:'uppercase', letterSpacing:'1px' }}>
            Progress
          </div>
          <div style={{ display:'flex', justifyContent:'space-between', marginBottom:7 }}>
            <span style={{ fontSize:12, color:'#8892b0' }}>Completion</span>
            <span style={{ fontSize:12, color:'#2563eb', fontWeight:600 }}>
              {todos.length ? Math.round((completedCount / todos.length) * 100) : 0}%
            </span>
          </div>
          <div style={{ background:'#1a1e38', borderRadius:10, height:5, overflow:'hidden' }}>
            <div style={{
              height:'100%', borderRadius:10,
              background:'#2563eb',
              width:`${todos.length ? (completedCount / todos.length) * 100 : 0}%`,
              transition:'width 0.6s ease'
            }} />
          </div>
          <div style={{ display:'flex', gap:20, marginTop:12 }}>
            {[['Active', activeCount], ['Done', completedCount], ['Total', todos.length]].map(([l, v]) => (
              <div key={l}>
                <div style={{ fontSize:19, fontWeight:800, color:'#e2e8f0' }}>{v}</div>
                <div style={{ fontSize:10, color:'#2d3460' }}>{l}</div>
              </div>
            ))}
          </div>
        </div>
      </aside>

      {/* ══ MAIN ══ */}
      <main style={{ flex:1, display:'flex', flexDirection:'column', overflow:'hidden' }}>

        {/* ── Top Bar ── */}
        <header style={{
          padding:'32px 36px 0', 
          display:'flex', alignItems:'flex-start', justifyContent:'space-between',
          background:'transparent', flexShrink:0, zIndex:10
        }}>
          <div>
            <div style={{ fontSize:13, color:'#73778b', marginBottom:12, fontWeight:500 }}>
              Personal management / My Week Timeline / <span style={{ color:'#e2e8f0' }}>My Tasks</span>
            </div>
            <h1 style={{ fontSize:36, fontWeight:700, color:'#ffffff', letterSpacing:'-0.5px', marginBottom:18 }}>
              {labelFilter ? `${labelFilter} Tasks` : 'My Tasks Board'}
            </h1>
            
            <div style={{ display:'flex', gap:28, borderBottom:'1px solid #232530', paddingBottom:14, marginBottom:5 }}>
              {['All', 'Active', 'Completed'].map(f => (
                <button
                  key={f}
                  className={`tab-underlined ${filter === f && !labelFilter ? 'active' : ''}`}
                  onClick={() => { setFilter(f); setLabelFilter(null) }}
                  style={{ 
                    background:'none', border:'none', color: (filter === f && !labelFilter) ? '#fff' : '#73778b',
                    fontSize:15, fontWeight: (filter === f && !labelFilter) ? 600 : 500, cursor:'pointer',
                    position:'relative', paddingBottom:4, outline:'none'
                  }}
                >
                  {f}
                  {(filter === f && !labelFilter) && (
                    <div style={{ position:'absolute', bottom:-14, left:0, right:0, height:2, background:'#fff', borderRadius:2 }} />
                  )}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display:'flex', alignItems:'center', gap:10, paddingTop: 10 }}>
            <button className="add-btn" style={{ borderRadius: 24, padding: '12px 28px', background:'#2563eb' }} onClick={() => { setShowForm(s => !s); setTimeout(() => inputRef.current?.focus(), 80) }}>
              Add Task
            </button>
            <div style={{ background:'#232530', borderRadius:'50%', width:44, height:44, display:'flex', alignItems:'center', justifyContent:'center', color:'#fff', cursor:'pointer' }}>
              •••
            </div>
          </div>
        </header>

        {/* ── Content ── */}
        <div style={{ flex:1, overflowY:'auto', padding:'20px 36px 40px' }}>

          {/* Error */}
          {error && (
            <div className="error-toast" style={{ marginBottom:18 }}>
              <span>⚠</span> {error}
            </div>
          )}

          {/* Add Task Form */}
          {showForm && (
            <form onSubmit={addTodo} style={{
              background:'#0f1122', border:'1px solid #1e2240',
              borderRadius:16, padding:'18px 20px', marginBottom:22,
              animation:'fadeInUp 0.25s ease'
            }}>
              <input
                ref={inputRef}
                className="task-input"
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                placeholder="Task title…"
                style={{ marginBottom:12 }}
              />
              <div style={{ display:'flex', gap:10, alignItems:'center' }}>
                {/* Label select */}
                <select
                  value={newLabel}
                  onChange={e => setNewLabel(e.target.value)}
                  style={{
                    background:'#151728', border:'1.5px solid #252840',
                    borderRadius:10, color:'#e2e8f0', padding:'9px 12px',
                    fontSize:13, outline:'none', cursor:'pointer', flex:1
                  }}
                >
                  {LABELS.map(l => (
                    <option key={l.name} value={l.name}>{l.name}</option>
                  ))}
                </select>

                <button type="submit" className="add-btn">Add</button>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  style={{
                    background:'transparent', border:'1.5px solid #252840',
                    color:'#4a5580', borderRadius:10, padding:'9px 14px',
                    fontSize:13, cursor:'pointer', transition:'color 0.2s'
                  }}
                >Cancel</button>
              </div>
            </form>
          )}

          {/* Filter Tabs + Week Nav */}
          <div style={{ display:'flex', alignItems:'center', justifyContent:'center', marginBottom:32, marginTop:4 }}>

            {/* Week navigation container */}
            <div style={{
              display:'flex', alignItems:'center', justifyContent:'space-between', 
              background:'#181a20', padding:'8px 8px', borderRadius:30, width:'100%'
            }}>
              <button onClick={() => setWeekOffset(w => w - 1)} style={{
                background:'#232530', border:'none',
                color:'#8892b0', borderRadius:'50%', width:38, height:38,
                cursor:'pointer', fontSize:18, display:'flex',
                alignItems:'center', justifyContent:'center',
                transition:'background 0.18s, color 0.18s'
              }}>‹</button>

              <div style={{ display:'flex', gap:20, alignItems:'center' }}>
                {labelFilter && (
                  <div style={{
                    display:'flex', alignItems:'center', gap:6,
                    background:'rgba(255,255,255,0.08)', borderRadius:16,
                    padding:'6px 14px', fontSize:13, color:'#fff'
                  }}>
                    <span className="dot" style={{ background: LABEL_MAP[labelFilter]?.color }} />
                    {labelFilter}
                    <span
                      style={{ cursor:'pointer', opacity:0.6, marginLeft:4, fontSize:12 }}
                      onClick={() => setLabelFilter(null)}
                    >✕</span>
                  </div>
                )}
                {!labelFilter && (
                  <span
                    style={{ fontSize:15, color:'#a0a4b8', cursor:'pointer', fontWeight:500 }}
                    onClick={() => setWeekOffset(0)}
                    title="Click to return to current week"
                  >
                    {fmtDateRange(weekDays)}
                  </span>
                )}
              </div>

              <button onClick={() => setWeekOffset(w => w + 1)} style={{
                background:'#232530', border:'none',
                color:'#8892b0', borderRadius:'50%', width:38, height:38,
                cursor:'pointer', fontSize:18, display:'flex',
                alignItems:'center', justifyContent:'center',
                transition:'background 0.18s, color 0.18s'
              }}>›</button>
            </div>
          </div>

          {/* Weekly Calendar Grid */}
          {loading ? (
            <div style={{ display:'grid', gridTemplateColumns:'repeat(7,1fr)', gap:12 }}>
              {Array.from({ length:7 }).map((_, i) => (
                <div key={i}>
                  <div className="skeleton" style={{ height:50, marginBottom:12 }} />
                  <SkeletonCard />
                  {i % 2 === 0 && <SkeletonCard />}
                </div>
              ))}
            </div>
          ) : (
            <>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(7,1fr)', gap:12 }}>
                {weekDays.map((d, di) => {
                  const isToday = sameDay(d, today)
                  const cards   = byDay[di]
                  return (
                    <div key={di}>
                      <div className="day-header">
                        <span className="day-name">{DAYS_SHORT[d.getDay()]}</span>
                        <span className={`day-num ${isToday ? 'today-num' : ''}`}>{d.getDate()}</span>
                      </div>
                      <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
                        {cards.length === 0
                          ? <div className="empty-cell">Empty Schedule</div>
                          : cards.map((todo, ci) => (
                              <TaskCard key={todo.id} todo={todo} index={ci} onToggle={toggleTodo} onDelete={deleteTodo} />
                            ))
                        }
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Outside this week */}
              {outsideWeek.length > 0 && (
                <div style={{ marginTop:32 }}>
                  <div style={{
                    fontSize:10.5, textTransform:'uppercase', letterSpacing:'1.2px',
                    color:'#2d3460', fontWeight:700, marginBottom:12,
                    display:'flex', alignItems:'center', gap:8
                  }}>
                    Other Weeks
                    <span style={{ background:'#1a1e36', borderRadius:20, padding:'1px 8px', fontSize:10 }}>
                      {outsideWeek.length}
                    </span>
                  </div>
                  <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(195px, 1fr))', gap:12 }}>
                    {outsideWeek.map((todo, i) => (
                      <TaskCard key={todo.id} todo={todo} index={i} onToggle={toggleTodo} onDelete={deleteTodo} />
                    ))}
                  </div>
                </div>
              )}

              {/* Empty state */}
              {filtered.length === 0 && (
                <div style={{ textAlign:'center', padding:'70px 20px', animation:'fadeInUp 0.4s ease' }}>
                  <div style={{ fontSize:44, marginBottom:14, opacity:0.5 }}>◌</div>
                  <div style={{ fontSize:17, fontWeight:700, color:'#c9d1f0', marginBottom:8 }}>
                    {labelFilter ? `No ${labelFilter} tasks` : filter === 'Completed' ? 'Nothing completed yet' : 'No tasks here'}
                  </div>
                  <div style={{ fontSize:13, color:'#2d3460' }}>
                    {filter === 'All' && !labelFilter ? 'Click "+ Add Task" to create your first task.' : 'Try a different filter.'}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  )
}

