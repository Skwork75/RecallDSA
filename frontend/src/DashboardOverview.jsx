import CalendarHeatmap from 'react-calendar-heatmap'
import 'react-calendar-heatmap/dist/styles.css'
import {
  Cell,
  CartesianGrid,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { AssessmentCard } from './AssessmentPages.jsx'

const chartColors = ['#8583ff', '#59c5a4', '#f1b65f', '#f27c82', '#56a6e8', '#bf83ed']

function StatSkeleton() {
  return <div className="metric-card stats-skeleton" aria-hidden="true"><i /><i /><i /></div>
}

function DashboardOverview({
  firstName,
  dashboardError,
  dashboardInsights,
  dashboardLoading,
  dashboardMetrics,
  onReview,
  todayRevisions,
}) {
  const patterns = (dashboardInsights?.patternStrength?.patterns ?? []).filter((pattern) => pattern.total_problems > 0)
  const activity = dashboardMetrics?.activity_last_90days ?? []
  const nextReviewDate = dashboardMetrics?.next_review_date
    ? new Date(dashboardMetrics.next_review_date).toLocaleDateString(undefined, { month: 'long', day: 'numeric' })
    : null

  return (
    <>
      <section className="dashboard-hero">
        <div>
          <p className="eyebrow">{dashboardMetrics?.onboarding_status === 'new' ? 'YOUR PRACTICE STARTS HERE' : 'YOUR NEXT REP'}</p>
          <h1>{dashboardMetrics?.onboarding_status === 'new' ? `Welcome to RecallDSA, ${firstName}.` : `Ready when you are, ${firstName}.`}</h1>
          <p className="dashboard-quote">“Every review is one more pattern your future self will not have to relearn.”</p>
        </div>
        <div className="streak-badge dashboard-streak"><span aria-hidden="true">🔥</span><div><strong>{dashboardMetrics ? dashboardMetrics.current_streak : '—'} day{dashboardMetrics?.current_streak === 1 ? '' : 's'}</strong><small>current streak</small></div></div>
      </section>

      {dashboardError && <div className="empty-state error-state" role="alert">{dashboardError}</div>}
      {dashboardMetrics?.onboarding_status === 'new' && (
        <div className="journey-banner"><span aria-hidden="true">✦</span><div><strong>Welcome! Start by connecting LeetCode or exploring famous sheets.</strong><p>Build your personal revision queue with problems you have already solved.</p></div></div>
      )}
      {dashboardMetrics && dashboardMetrics.total_problems_tracked > 0 && dashboardMetrics.problems_due_today === 0 && (
        <div className="journey-banner caught-up-banner"><span aria-hidden="true">✓</span><div><strong>All caught up!{nextReviewDate ? ` Next review on ${nextReviewDate}.` : ''}</strong><p>Keep the momentum going by adding another problem or exploring a new pattern.</p></div></div>
      )}

      <section className="metrics-row dashboard-stats-row" aria-label="Your revision dashboard">
        {dashboardLoading && [0, 1, 2, 3].map((item) => <StatSkeleton key={item} />)}
        {!dashboardLoading && dashboardMetrics && <>
          <article className="metric-card metric-featured"><span className="metric-icon" aria-hidden="true">◎</span><strong>{dashboardMetrics.total_problems_tracked}</strong><small>problems tracked</small><div className="metric-line" /></article>
          <article className="metric-card"><span className="metric-icon" aria-hidden="true">◌</span><strong>{dashboardMetrics.problems_due_today}</strong><small>problems due today</small><a href="#today-revisions">Review queue <span>↗</span></a></article>
          <article className="metric-card"><span className="metric-icon" aria-hidden="true">🔥</span><strong>{dashboardMetrics.current_streak} day{dashboardMetrics.current_streak === 1 ? '' : 's'}</strong><small>best: {dashboardMetrics.longest_streak} day{dashboardMetrics.longest_streak === 1 ? '' : 's'}</small></article>
          <article className="metric-card"><span className="metric-icon" aria-hidden="true">✓</span><strong>{dashboardMetrics.revision_completion_7days}%</strong><small>revision completion · last 7 days</small><div className="progress-track"><span style={{ width: `${dashboardMetrics.revision_completion_7days}%` }} /></div></article>
        </>}
      </section>

      <section className="dashboard-quick-actions" aria-labelledby="quick-actions-title">
        <div className="dashboard-section-heading"><div><p className="eyebrow">A GOOD NEXT STEP</p><h2 id="quick-actions-title">Quick actions</h2></div></div>
        <div className="quick-action-grid">
          {dashboardMetrics?.total_problems_tracked === 0 && <>
            <a className="quick-action-card quick-action-primary" href="/sheets"><span aria-hidden="true">▤</span><div><strong>Explore Sheets</strong><small>Start with a curated interview roadmap.</small></div><b aria-hidden="true">↗</b></a>
            <a className="quick-action-card" href="#library"><span aria-hidden="true">↻</span><div><strong>Sync LeetCode</strong><small>{dashboardMetrics.has_leetcode_connected ? 'Your imported LeetCode problems are connected.' : 'LeetCode syncing is not connected yet. Browse problems or explore sheets to get started.'}</small></div><b aria-hidden="true">{dashboardMetrics.has_leetcode_connected ? 'View import ↗' : 'Browse problems ↗'}</b></a>
          </>}
          {dashboardMetrics?.total_problems_tracked > 0 && dashboardMetrics.problems_due_today === 0 && <>
            <a className="quick-action-card quick-action-primary" href="#library"><span aria-hidden="true">⌘</span><div><strong>Browse Library</strong><small>Find a new pattern to practice.</small></div><b aria-hidden="true">↗</b></a>
            <a className="quick-action-card" href="/sheets"><span aria-hidden="true">＋</span><div><strong>Add More</strong><small>Grow your personal revision queue.</small></div><b aria-hidden="true">↗</b></a>
          </>}
          {dashboardMetrics?.problems_due_today > 0 && <a className="quick-action-card quick-action-primary review-action" href="#today-revisions"><span aria-hidden="true">◷</span><div><strong>Start Today's Review</strong><small>{dashboardMetrics.problems_due_today} problem{dashboardMetrics.problems_due_today === 1 ? '' : 's'} ready to revisit · about {dashboardMetrics.problems_due_today * 5} min</small></div><b aria-hidden="true">Start ↗</b></a>}
        </div>
      </section>

      <section className="analytics-panel dashboard-panel dashboard-activity-panel">
        <div className="analytics-panel-heading"><div><p className="eyebrow">CONSISTENCY</p><h2>Activity · last 90 days</h2></div><span className="result-count">{activity.reduce((sum, day) => sum + day.count, 0)} reviews</span></div>
        {!dashboardLoading && activity.length > 0 && <div className="analytics-heatmap" aria-label="Daily review activity for the last 90 days"><CalendarHeatmap endDate={new Date(`${activity[activity.length - 1].date}T00:00:00`)} startDate={new Date(`${activity[0].date}T00:00:00`)} values={activity.map((day) => ({ ...day, date: new Date(`${day.date}T00:00:00`) }))} classForValue={(day) => `heatmap-level-${!day || day.count === 0 ? 0 : day.count < 3 ? 1 : day.count < 6 ? 2 : day.count < 10 ? 3 : 4}`} tooltipDataAttrs={(day) => ({ 'aria-label': `${day.date.toLocaleDateString()}: ${day.count} reviews` })} /></div>}
        {dashboardMetrics && <p className="dashboard-practice-summary">{dashboardMetrics.patterns_covered} of 25 patterns · {dashboardMetrics.sheets_in_progress} sheets in progress · this week: {dashboardMetrics.this_week_solved} solved, {dashboardMetrics.this_week_reviewed} reviewed</p>}
      </section>

      <div className="dashboard-insight-grid">
        <section className="analytics-panel dashboard-panel">
          <div className="analytics-panel-heading"><div><p className="eyebrow">RECALL QUALITY</p><h2>Confidence trend</h2></div><span className="result-count">Last 30 days</span></div>
          {!dashboardInsights?.confidenceTrend?.some((day) => day.average_confidence !== null) ? <div className="analytics-empty">Your confidence trend will appear after your first review.</div> : <div className="analytics-chart"><ResponsiveContainer width="100%" height={245}><LineChart data={dashboardInsights.confidenceTrend} margin={{ top: 12, right: 12, left: -16, bottom: 0 }}><CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 4" /><XAxis dataKey="date" tick={{ fill: 'var(--muted)', fontSize: 10 }} tickFormatter={(date) => date.slice(5)} minTickGap={24} /><YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} tick={{ fill: 'var(--muted)', fontSize: 10 }} /><Tooltip contentStyle={{ background: 'var(--white)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--ink)' }} formatter={(value) => [`${Number(value).toFixed(1)} / 5`, 'Confidence']} /><Line connectNulls dataKey="average_confidence" dot={{ r: 3, fill: 'var(--green)' }} stroke="var(--green)" strokeWidth={3} type="monotone" /></LineChart></ResponsiveContainer></div>}
        </section>
        <section className="analytics-panel dashboard-panel">
          <div className="analytics-panel-heading"><div><p className="eyebrow">YOUR PRACTICE PLAN</p><h2>Pattern distribution</h2></div><span className="result-count">{dashboardMetrics?.patterns_covered ?? 0} / 25 covered</span></div>
          {!patterns.length ? <div className="analytics-empty">Add problems from a sheet to see your pattern distribution.</div> : <div className="analytics-donut-layout"><div className="analytics-chart analytics-donut"><ResponsiveContainer width="100%" height={230}><PieChart><Pie data={patterns} dataKey="total_problems" nameKey="pattern_name" innerRadius={58} outerRadius={88} paddingAngle={3}>{patterns.map((pattern, index) => <Cell fill={chartColors[index % chartColors.length]} key={pattern.pattern_id} />)}</Pie><Tooltip contentStyle={{ background: 'var(--white)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--ink)' }} formatter={(value, _name, item) => [value, item.payload.pattern_name]} /></PieChart></ResponsiveContainer></div><ul className="analytics-legend">{patterns.map((pattern, index) => <li key={pattern.pattern_id}><span style={{ background: chartColors[index % chartColors.length] }} /><span>{pattern.pattern_name}</span><strong>{pattern.total_problems}</strong></li>)}</ul></div>}
        </section>
      </div>

      <section className="revision-section dashboard-revision-section" id="today-revisions">
        <div className="section-heading"><div><p className="eyebrow">TODAY'S REVISION</p><h2>{dashboardLoading ? "Loading today's revisions…" : todayRevisions.length === 0 ? 'Nothing due today' : `You have ${todayRevisions.length} problem${todayRevisions.length === 1 ? '' : 's'} to revise.`}</h2></div><span className="result-count">{dashboardLoading ? '—' : `${todayRevisions.length} due`}</span></div>
        {dashboardLoading && <div className="revision-skeletons" aria-label="Loading today's revisions"><i /><i /><i /></div>}
        {!dashboardLoading && todayRevisions.length === 0 ? <div className="empty-state">{dashboardMetrics?.total_problems_tracked ? `All caught up!${nextReviewDate ? ` Next review on ${nextReviewDate}.` : ''}` : 'Your review queue is empty. Explore a sheet or add a problem to begin.'}</div> : !dashboardLoading && <div className="revision-list">{todayRevisions.map((progress) => <article className="revision-card" key={progress.id}><div className="revision-card-header"><span className={`difficulty-dot ${progress.problem.difficulty.toLowerCase()}`} /><span className="difficulty-label">{progress.problem.difficulty}</span></div><h3>{progress.problem.title}</h3><p className="pattern-label">{progress.problem.pattern?.p_name || 'Uncategorized pattern'}</p><div className="revision-card-footer"><button className="primary-button" onClick={() => onReview(progress.problem)} type="button">Start Revision</button></div></article>)}</div>}
      </section>

      <div className="dashboard-weekly-assessment"><AssessmentCard /></div>

      <section className="dashboard-weak-areas">
        <div className="dashboard-section-heading"><div><p className="eyebrow">PERSONALIZED FOCUS</p><h2>Weak areas</h2></div><a href="/analytics">View analytics ↗</a></div>
        {!dashboardInsights ? <div className="revision-skeletons" aria-label="Loading recommendations"><i /><i /></div> : dashboardInsights.recommendations.length === 0 ? <div className="analytics-empty">No urgent weak spots yet. Keep reviewing to unlock focused recommendations.</div> : <div className="weak-area-list">{dashboardInsights.recommendations.slice(0, 3).map((recommendation, index) => <article className="weak-area-card" key={`${recommendation.type}-${recommendation.pattern_id ?? index}`}><span className={`weak-area-priority priority-${recommendation.priority}`}>{recommendation.priority}</span><div><strong>{recommendation.title}</strong><p>{recommendation.description}</p></div><a href={recommendation.type === 'overdue' ? '#today-revisions' : '/analytics'}>{recommendation.action_label || 'Review'} <span aria-hidden="true">↗</span></a></article>)}</div>}
      </section>
    </>
  )
}

export default DashboardOverview
