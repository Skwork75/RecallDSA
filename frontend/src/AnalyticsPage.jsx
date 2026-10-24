import { useEffect, useMemo, useState } from 'react'
import CalendarHeatmap from 'react-calendar-heatmap'
import 'react-calendar-heatmap/dist/styles.css'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAuth } from './context/useAuth.js'

const chartColors = ['#8583ff', '#59c5a4', '#f1b65f', '#f27c82', '#56a6e8', '#bf83ed']
const recommendationLabels = {
  overdue: 'OVERDUE',
  weak_pattern: 'WEAK PATTERN',
  declining: 'DECLINING',
  not_started: 'NOT STARTED',
}

function ChartPanel({ title, eyebrow, children, className = '' }) {
  return (
    <section className={`analytics-panel ${className}`}>
      <div className="analytics-panel-heading"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2></div></div>
      {children}
    </section>
  )
}

function AnalyticsPage() {
  const { authenticatedRequest } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.all([
      authenticatedRequest('/api/analytics/pattern-strength/'),
      authenticatedRequest('/api/analytics/recommendations/'),
      authenticatedRequest('/api/analytics/activity-heatmap/'),
      authenticatedRequest('/api/analytics/confidence-trend/'),
    ]).then(([patternStrength, recommendations, activity, confidenceTrend]) => {
      if (active) setData({ patternStrength, recommendations, activity, confidenceTrend })
    }).catch((requestError) => {
      if (active) setError(requestError.message)
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [authenticatedRequest])

  const rankedPatterns = useMemo(
    () => (data?.patternStrength.patterns ?? []).filter((pattern) => pattern.average_confidence !== null),
    [data],
  )
  const distribution = useMemo(
    () => (data?.patternStrength.patterns ?? []).filter((pattern) => pattern.total_problems > 0),
    [data],
  )
  const heatmapValues = useMemo(
    () => (data?.activity ?? []).map((day) => ({ date: day.date, count: day.count })),
    [data],
  )
  const firstHeatmapDay = heatmapValues[0]?.date
  const lastHeatmapDay = heatmapValues[heatmapValues.length - 1]?.date
  const dayLabels = useMemo(() => ({
    start: firstHeatmapDay ? new Date(`${firstHeatmapDay}T00:00:00`) : new Date(),
    end: lastHeatmapDay ? new Date(`${lastHeatmapDay}T00:00:00`) : new Date(),
  }), [firstHeatmapDay, lastHeatmapDay])

  return (
    <main className="analytics-page">
      <div className="analytics-content">
          <section className="analytics-intro">
            <p className="eyebrow">LEARN FROM YOUR REVIEWS</p>
            <h1>Patterns, not guesswork.</h1>
            <p>See where your recall is growing, where to focus next, and how consistently you have been practicing.</p>
          </section>

          {loading && <div className="analytics-state" role="status">Loading your analytics…</div>}
          {error && <div className="analytics-state analytics-error" role="alert">{error}</div>}

          {!loading && !error && data && (
            <>
              <section className="analytics-summary" aria-label="Analytics summary">
                <article><span>Tracked problems</span><strong>{data.patternStrength.summary.total_problems}</strong></article>
                <article><span>Patterns with reviews</span><strong>{rankedPatterns.length}</strong></article>
                <article><span>Overall confidence</span><strong>{data.patternStrength.summary.average_confidence === null ? '—' : `${data.patternStrength.summary.average_confidence}/5`}</strong></article>
              </section>

              <div className="analytics-chart-grid">
                <ChartPanel className="analytics-panel-wide" eyebrow="RECALL STRENGTH" title="Confidence by pattern">
                  {rankedPatterns.length === 0 ? <div className="analytics-empty">Review problems from different patterns to see your confidence breakdown.</div> : (
                    <div className="analytics-chart confidence-chart">
                      <ResponsiveContainer width="100%" height={Math.max(250, rankedPatterns.length * 48)}>
                        <BarChart data={rankedPatterns} layout="vertical" margin={{ top: 6, right: 18, left: 8, bottom: 4 }}>
                          <CartesianGrid stroke="var(--chart-grid)" horizontal={false} />
                          <XAxis type="number" domain={[0, 5]} tick={{ fill: 'var(--muted)', fontSize: 11 }} />
                          <YAxis type="category" dataKey="pattern_name" width={130} tick={{ fill: 'var(--ink)', fontSize: 11 }} />
                          <Tooltip contentStyle={{ background: 'var(--white)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--ink)' }} formatter={(value) => [`${Number(value).toFixed(1)} / 5`, 'Confidence']} />
                          <Bar dataKey="average_confidence" radius={[0, 5, 5, 0]} barSize={20}>
                            {rankedPatterns.map((pattern, index) => <Cell fill={chartColors[index % chartColors.length]} key={pattern.pattern_id} />)}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </ChartPanel>

                <ChartPanel eyebrow="LAST 30 DAYS" title="Confidence trend">
                  {data.confidenceTrend.every((day) => day.average_confidence === null) ? <div className="analytics-empty">Your daily confidence trend will appear after your first review.</div> : (
                    <div className="analytics-chart">
                      <ResponsiveContainer width="100%" height={280}>
                        <LineChart data={data.confidenceTrend} margin={{ top: 12, right: 12, left: -16, bottom: 0 }}>
                          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 4" />
                          <XAxis dataKey="date" tick={{ fill: 'var(--muted)', fontSize: 10 }} tickFormatter={(date) => date.slice(5)} minTickGap={24} />
                          <YAxis domain={[1, 5]} ticks={[1, 2, 3, 4, 5]} tick={{ fill: 'var(--muted)', fontSize: 10 }} />
                          <Tooltip labelFormatter={(date) => date} contentStyle={{ background: 'var(--white)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--ink)' }} formatter={(value) => [`${Number(value).toFixed(1)} / 5`, 'Average confidence']} />
                          <Line connectNulls dataKey="average_confidence" dot={{ r: 3, fill: 'var(--green)' }} stroke="var(--green)" strokeWidth={3} type="monotone" />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </ChartPanel>

                <ChartPanel eyebrow="YOUR PRACTICE PLAN" title="Pattern distribution">
                  {distribution.length === 0 ? <div className="analytics-empty">Add problems from a DSA sheet or your library to see pattern distribution.</div> : (
                    <div className="analytics-donut-layout">
                      <div className="analytics-chart analytics-donut">
                        <ResponsiveContainer width="100%" height={250}>
                          <PieChart>
                            <Pie data={distribution} dataKey="total_problems" nameKey="pattern_name" innerRadius={64} outerRadius={94} paddingAngle={3}>
                              {distribution.map((pattern, index) => <Cell fill={chartColors[index % chartColors.length]} key={pattern.pattern_id} />)}
                            </Pie>
                            <Tooltip contentStyle={{ background: 'var(--white)', border: '1px solid var(--line)', borderRadius: 8, color: 'var(--ink)' }} formatter={(value, _name, item) => [value, item.payload.pattern_name]} />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                      <ul className="analytics-legend">{distribution.map((pattern, index) => <li key={pattern.pattern_id}><span style={{ background: chartColors[index % chartColors.length] }} /><span>{pattern.pattern_name}</span><strong>{pattern.total_problems}</strong></li>)}</ul>
                    </div>
                  )}
                </ChartPanel>

                <ChartPanel className="analytics-panel-wide" eyebrow="CONSISTENCY" title="Review activity">
                  <div className="analytics-heatmap-summary">
                    <span>{data.activity.reduce((sum, day) => sum + day.count, 0)} reviews in the last 90 days</span>
                    <div className="heatmap-scale" aria-label="Less to more activity"><span>Less</span>{[0, 1, 2, 3, 4].map((level) => <i className={`heatmap-level-${level}`} key={level} />)}<span>More</span></div>
                  </div>
                  <div className="analytics-heatmap" aria-label="Daily review activity for the last 90 days">
                    <CalendarHeatmap
                      endDate={dayLabels.end}
                      startDate={dayLabels.start}
                      values={heatmapValues.map((day) => ({ ...day, date: new Date(`${day.date}T00:00:00`) }))}
                      classForValue={(day) => `heatmap-level-${!day || day.count === 0 ? 0 : day.count < 3 ? 1 : day.count < 6 ? 2 : day.count < 10 ? 3 : 4}`}
                      tooltipDataAttrs={(day) => ({ 'aria-label': `${day.date.toLocaleDateString()}: ${day.count} reviews` })}
                    />
                  </div>
                </ChartPanel>
              </div>

              <section className="analytics-recommendations">
                <div className="analytics-section-heading"><div><p className="eyebrow">WHAT TO DO NEXT</p><h2>Recommended actions</h2></div><span>{data.recommendations.length} action{data.recommendations.length === 1 ? '' : 's'}</span></div>
                {data.recommendations.length === 0 ? <div className="analytics-empty">You are on track. Keep reviewing to unlock personalized recommendations.</div> : (
                  <div className="recommendation-list">
                    {data.recommendations.map((recommendation) => {
                      const firstProblem = recommendation.problems[0]
                      return (
                        <article className="recommendation-card" key={`${recommendation.type}-${recommendation.pattern_id ?? 'uncategorized'}`}>
                          <div className={`recommendation-priority priority-${recommendation.priority}`} aria-label={`Priority ${recommendation.priority}`}>{recommendation.priority}</div>
                          <div className="recommendation-copy">
                            <span className="recommendation-type">{recommendationLabels[recommendation.type]}</span>
                            <h3>{recommendation.title}</h3>
                            <p>{recommendation.description}</p>
                            <small>{recommendation.problem_ids.length} suggested problem{recommendation.problem_ids.length === 1 ? '' : 's'} · IDs {recommendation.problem_ids.join(', ')}</small>
                          </div>
                          {firstProblem && <a className="analytics-action-button" href={`/dashboard?review=${firstProblem.id}`}>{recommendation.action_label}<span aria-hidden="true">↗</span></a>}
                        </article>
                      )
                    })}
                  </div>
                )}
              </section>
            </>
          )}
      </div>
    </main>
  )
}

export default AnalyticsPage
