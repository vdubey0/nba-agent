import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  applyAutomaticReview,
  getAnalyticsAccuracy,
  getAnalyticsLatencyDistribution,
  getAnalyticsPerformance,
  getAnalyticsQuestions,
  getAnalyticsSummary,
  invokeAutomaticReview,
} from '../../services/api';
import BarChart from './BarChart';
import MetricTile from './MetricTile';

const SOURCES = [
  { value: '', label: 'All sources' },
  { value: 'query_family', label: '/query' },
  { value: 'local_family', label: 'Local chat' },
];

const formatMs = (value) => `${Math.round(Number(value) || 0).toLocaleString()} ms`;
const formatPct = (value) => `${Math.round((Number(value) || 0) * 100)}%`;
const formatNumber = (value) => Math.round(Number(value) || 0).toLocaleString();
const attentionQuestionCardClass = 'rounded-lg border border-slate-200 bg-white p-3';
const attentionOutcomePillClass = 'rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-700';
const outcomeClassName = (outcome) => (
  outcome === 'error'
    ? 'rounded-full bg-red-100 px-2 py-1 font-medium text-red-700'
    : outcome === 'incorrect'
      ? 'rounded-full bg-amber-100 px-2 py-1 font-medium text-amber-700'
      : outcome === 'correct'
        ? 'rounded-full bg-emerald-100 px-2 py-1 font-medium text-emerald-700'
        : 'rounded-full bg-slate-100 px-2 py-1 font-medium text-slate-700'
);

const AnalyticsDashboard = () => {
  const [days, setDays] = useState(30);
  const [source, setSource] = useState('');
  const [summary, setSummary] = useState(null);
  const [performance, setPerformance] = useState(null);
  const [latencyDistribution, setLatencyDistribution] = useState(null);
  const [accuracy, setAccuracy] = useState(null);
  const [questions, setQuestions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [reviewingId, setReviewingId] = useState(null);
  const [reviewSession, setReviewSession] = useState(null);
  const [reviewActionError, setReviewActionError] = useState(null);
  const [savingReview, setSavingReview] = useState(false);
  const [reviewAllProgress, setReviewAllProgress] = useState(null);
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [selectedError, setSelectedError] = useState(null);
  const [showLatencyDetails, setShowLatencyDetails] = useState(false);
  const appliedReviewIdsRef = useRef(new Set());
  const appliedReviewEventsRef = useRef(new Map());

  const loadAnalytics = useCallback(async (active = true, { silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const [summaryData, performanceData, latencyData, accuracyData, questionsData] = await Promise.all([
        getAnalyticsSummary(days, source),
        getAnalyticsPerformance(days, source),
        getAnalyticsLatencyDistribution(days, source),
        getAnalyticsAccuracy(days, source),
        getAnalyticsQuestions(days, source),
      ]);
      if (!active) return;
      const appliedReviewIds = appliedReviewIdsRef.current;
      const appliedReviewEvents = appliedReviewEventsRef.current;
      const filteredAccuracyData = {
        ...accuracyData,
        review_queue: (accuracyData.review_queue || []).filter((event) => !appliedReviewIds.has(event.id)),
      };
      const filteredQuestionsData = {
        ...questionsData,
        recent_events: (questionsData.recent_events || []).map((event) => (
          appliedReviewEvents.has(event.id)
            ? {
                ...event,
                ...appliedReviewEvents.get(event.id),
                evaluation: {
                  ...(event.evaluation || {}),
                  ...(appliedReviewEvents.get(event.id)?.evaluation || {}),
                },
              }
            : event
        )),
      };
      setSummary(summaryData);
      setPerformance(performanceData);
      setLatencyDistribution(latencyData);
      setAccuracy(filteredAccuracyData);
      setQuestions(filteredQuestionsData);
    } catch (err) {
      if (active) setError(err.message || 'Failed to load analytics');
    } finally {
      if (active && !silent) setLoading(false);
    }
  }, [days, source]);

  useEffect(() => {
    let active = true;
    loadAnalytics(active);
    const refreshTimer = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        loadAnalytics(active, { silent: true });
      }
    }, 5000);
    return () => {
      active = false;
      window.clearInterval(refreshTimer);
    };
  }, [days, source, loadAnalytics]);

  const outcomeRows = useMemo(() => {
    const outcomes = accuracy?.outcomes || [];
    return outcomes.map((row) => ({ label: row.outcome, count: row.count }));
  }, [accuracy]);

  const handleInvokeReview = async (event) => {
    setReviewingId(event.id);
    setReviewActionError(null);
    try {
      const data = await invokeAutomaticReview(event.id);
      setReviewSession({
        mode: 'single',
        index: 0,
        items: [{
          event: data.event,
          review: data.review,
          selectedOutcome: null,
          status: 'pending',
        }],
      });
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Automatic review failed');
    } finally {
      setReviewingId(null);
    }
  };

  const handleReviewAll = async () => {
    const queue = accuracy?.review_queue || [];
    if (queue.length === 0) return;

    setReviewAllProgress({ current: 0, total: queue.length });
    setReviewActionError(null);
    setError(null);
    const reviewedItems = [];

    for (let index = 0; index < queue.length; index += 1) {
      setReviewAllProgress({ current: index + 1, total: queue.length });
      try {
        const data = await invokeAutomaticReview(queue[index].id);
        reviewedItems.push({
          event: data.event,
          review: data.review,
          selectedOutcome: null,
          status: 'pending',
        });
      } catch (err) {
        reviewedItems.push({
          event: queue[index],
          review: {
            classification: 'ambiguous',
            confidence: 'unknown',
            rationale: err.response?.data?.detail || err.message || 'Automatic review failed.',
          },
          selectedOutcome: null,
          status: 'failed',
        });
      }
    }

    setReviewAllProgress(null);
    if (reviewedItems.length === 0) {
      setError('No review queue items could be reviewed.');
      return;
    }
    setReviewSession({
      mode: 'bulk',
      index: 0,
      items: reviewedItems,
    });
  };

  const updateCurrentReviewItem = (updates) => {
    setReviewSession((current) => {
      if (!current) return current;
      const items = current.items.map((item, index) => (
        index === current.index ? { ...item, ...updates } : item
      ));
      return { ...current, items };
    });
  };

  const updateAnalyticsAfterReview = (event, outcome, updatedEvent = null) => {
    const reviewedEvent = updatedEvent || {
      ...event,
      evaluation: {
        ...(event.evaluation || {}),
        status: 'completed',
        outcome,
        evaluation_method: 'llm_assisted_manual_review',
      },
      outcome,
    };
    appliedReviewIdsRef.current.add(event.id);
    appliedReviewEventsRef.current.set(event.id, reviewedEvent);

    setAccuracy((current) => {
      if (!current) return current;
      const reviewQueue = (current.review_queue || []).filter((item) => item.id !== event.id);
      const existingErrors = current.errors || [];
      const errors = ['error', 'incorrect'].includes(outcome)
        ? [
            {
              ...reviewedEvent,
              outcome,
              created_at: reviewedEvent.created_at || event.created_at || new Date().toISOString(),
            },
            ...existingErrors.filter((item) => item.id !== event.id),
          ]
        : existingErrors.filter((item) => item.id !== event.id);

      return {
        ...current,
        review_queue: reviewQueue,
        errors,
      };
    });

    setQuestions((current) => {
      if (!current) return current;
      return {
        ...current,
        recent_events: (current.recent_events || []).map((item) => (
          item.id === event.id
            ? {
                ...item,
                ...reviewedEvent,
                evaluation: {
                  ...(item.evaluation || {}),
                  ...(reviewedEvent.evaluation || {}),
                  outcome,
                },
              }
            : item
        )),
      };
    });
  };

  const refreshAnalyticsInBackground = () => {
    loadAnalytics(true).catch((err) => {
      setError(err.message || 'Failed to refresh analytics');
    });
  };

  const goToNextReview = () => {
    setReviewActionError(null);
    setReviewSession((current) => {
      if (!current) return current;
      if (current.index < current.items.length - 1) {
        return { ...current, index: current.index + 1 };
      }
      return null;
    });
    const currentSession = reviewSession;
    if (currentSession?.index >= currentSession.items.length - 1) {
      refreshAnalyticsInBackground();
    }
  };

  const applyCurrentReview = async (outcome, reviewer = 'user') => {
    const currentItem = reviewSession?.items?.[reviewSession.index];
    if (!currentItem || !outcome) return;
    setSavingReview(true);
    setReviewActionError(null);
    try {
      const result = await applyAutomaticReview(currentItem.event.id, outcome, currentItem.review, reviewer);
      const storedOutcome = result?.evaluation?.outcome || outcome;
      updateCurrentReviewItem({ status: 'applied', appliedOutcome: storedOutcome });
      updateAnalyticsAfterReview(currentItem.event, storedOutcome, result?.event);
      goToNextReview();
    } catch (err) {
      setReviewActionError(err.response?.data?.detail || err.message || 'Failed to apply review');
    } finally {
      setSavingReview(false);
    }
  };

  const closeReviewModal = async () => {
    if (!reviewSession || savingReview) return;
    if (reviewSession.mode === 'bulk') {
      setReviewSession(null);
      refreshAnalyticsInBackground();
      return;
    }

    const currentItem = reviewSession.items[reviewSession.index];
    const defaultOutcome = currentItem.review?.classification;
    if (currentItem.selectedOutcome) {
      await applyCurrentReview(currentItem.selectedOutcome, 'user_override');
      return;
    }
    if (defaultOutcome && defaultOutcome !== 'ambiguous') {
      await applyCurrentReview(defaultOutcome, 'llm_default');
      return;
    }
    setReviewActionError('Ambiguous classifications require a reviewer decision.');
  };

  const skipCurrentReview = async () => {
    updateCurrentReviewItem({ status: 'skipped' });
    goToNextReview();
  };

  const goBackReview = () => {
    setReviewActionError(null);
    setReviewSession((current) => {
      if (!current || current.index === 0) return current;
      return { ...current, index: current.index - 1 };
    });
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <div className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Chatbot Analytics</h1>
            <p className="text-sm text-slate-600">Internal performance, correctness, and question intelligence.</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
            <select
              value={source}
              onChange={(event) => setSource(event.target.value)}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm"
            >
              {SOURCES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-7xl px-6 py-6">
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}
        {loading && <div className="mb-4 text-sm text-slate-500">Loading analytics...</div>}

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <MetricTile label="Queries" value={summary?.total_queries ?? 0} detail="Tracked API, local, and benchmark traffic" />
          <MetricTile
            label="Avg latency"
            value={formatMs(summary?.average_latency_ms)}
            detail="User-facing path only"
            action={(
              <button
                type="button"
                onClick={() => setShowLatencyDetails(true)}
                className="text-xs font-semibold text-cyan-700 transition hover:text-cyan-900 hover:underline"
              >
                See details
              </button>
            )}
          />
          <MetricTile label="Error rate" value={formatPct(summary?.error_rate)} detail="Deterministic outcome" />
          <MetricTile label="Objective accuracy" value={formatPct(summary?.objective_accuracy_rate)} detail={`${summary?.verifiable_count ?? 0} verifiable`} />
          <MetricTile label="Pending jobs" value={summary?.pending_jobs ?? 0} detail="Async analytics queue" />
        </section>

        <section className="mt-6 grid gap-6 xl:grid-cols-2">
          <Panel title="Latency By Type Of Question" subtitle="Average latency grouped by detected intent.">
            <ScrollArea>
              <BarChart data={questions?.intents || []} labelKey="intent" valueKey="avg_latency_ms" valueLabel={formatMs} />
            </ScrollArea>
          </Panel>
          <Panel title="Latency By Complexity" subtitle="Average latency grouped by query complexity.">
            <ScrollArea>
              <BarChart data={questions?.complexity || []} labelKey="complexity" valueKey="avg_latency_ms" valueLabel={formatMs} />
            </ScrollArea>
          </Panel>
        </section>

        <section className="mt-6 grid gap-6 xl:grid-cols-3">
          <Panel title="Query Volume" subtitle="Daily tracked volume.">
            <ScrollArea compact>
              <BarChart data={performance?.by_day || []} labelKey="day" valueKey="query_count" />
            </ScrollArea>
          </Panel>
          <Panel title="Accuracy Outcomes" subtitle="Objective states, no subjective scoring.">
            <ScrollArea compact>
              <BarChart data={outcomeRows} labelKey="label" valueKey="count" />
            </ScrollArea>
          </Panel>
          <Panel title="Source Mix" subtitle="API, local, and benchmark traffic.">
            <ScrollArea compact>
              <BarChart data={performance?.by_source || []} labelKey="source" valueKey="query_count" />
            </ScrollArea>
          </Panel>
        </section>

        <section className="mt-6">
          <Panel
            title="Review Queue"
            subtitle="Unresolved answers awaiting sanity review."
            action={(accuracy?.review_queue || []).length > 0 && (
              <button
                type="button"
                onClick={handleReviewAll}
                disabled={Boolean(reviewAllProgress)}
                className="rounded-md border border-slate-900 bg-white px-3 py-2 text-sm font-medium text-slate-900 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:border-slate-300 disabled:text-slate-400"
              >
                {reviewAllProgress ? `Reviewing ${reviewAllProgress.current}/${reviewAllProgress.total}` : 'Review All'}
              </button>
            )}
          >
            <ScrollArea>
              <div className="space-y-3">
              {(accuracy?.review_queue || []).map((event) => (
                <div key={event.id} className={attentionQuestionCardClass}>
                  <div className="flex items-center justify-between gap-3">
                    <span className={`${outcomeClassName(event.outcome)} text-xs`}>
                      {event.outcome}
                    </span>
                    <span className="text-xs text-slate-500">{formatMs(event.latency_ms)}</span>
                  </div>
                  <p className="mt-2 text-sm font-medium text-slate-800">{event.user_message}</p>
                  {event.bot_response_preview && (
                    <MarkdownAnswer compact>{event.bot_response_preview}</MarkdownAnswer>
                  )}
                  <button
                    type="button"
                    onClick={() => handleInvokeReview(event)}
                    disabled={reviewingId === event.id}
                    className="mt-3 inline-flex items-center rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
                  >
                    {reviewingId === event.id ? 'Reviewing...' : 'Invoke automatic review'}
                  </button>
                </div>
              ))}
              {(accuracy?.review_queue || []).length === 0 && <Empty />}
              </div>
            </ScrollArea>
          </Panel>
        </section>

        <section className="mt-6 grid gap-6 xl:grid-cols-2">
          <Panel title="Recurring Question Clusters" subtitle="Similarity groups from async analysis.">
            <ScrollArea>
              <div className="space-y-3">
              {(questions?.clusters || []).map((cluster) => (
                <div key={cluster.id} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => setSelectedCluster(cluster)}
                      className="text-left text-sm font-semibold text-cyan-700 transition hover:text-cyan-900 hover:underline"
                    >
                      {cluster.label || 'cluster'}
                    </button>
                    <span className="text-xs text-slate-500">{cluster.query_count} queries</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">{cluster.representative_question}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                    <span>{formatPct(cluster.accuracy_rate)} accuracy</span>
                    <span>{formatPct(cluster.error_rate)} error rate</span>
                    <span>{formatMs(cluster.avg_latency_ms)} avg latency</span>
                  </div>
                </div>
              ))}
              {(questions?.clusters || []).length === 0 && <Empty />}
              </div>
            </ScrollArea>
          </Panel>

          <Panel title="Errors" subtitle="Errored questions plus reviewed incorrect answers.">
            <ScrollArea>
              <div className="space-y-3">
                {(accuracy?.errors || []).map((event) => (
                  <div
                    key={event.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedError(event)}
                    onKeyDown={(keyboardEvent) => {
                      if (keyboardEvent.key === 'Enter' || keyboardEvent.key === ' ') {
                        keyboardEvent.preventDefault();
                        setSelectedError(event);
                      }
                    }}
                    className={`${attentionQuestionCardClass} block w-full text-left transition hover:border-red-200 hover:bg-red-50/40 focus:outline-none focus:ring-2 focus:ring-red-200`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className={attentionOutcomePillClass}>
                        {event.outcome}
                      </span>
                      <span className="text-xs text-slate-500">
                        {event.created_at ? new Date(event.created_at).toLocaleString() : ''}
                      </span>
                    </div>
                    <p className="mt-2 text-sm font-medium text-slate-800">{event.user_message}</p>
                    {event.bot_response_preview && (
                      <MarkdownAnswer compact>{event.bot_response_preview}</MarkdownAnswer>
                    )}
                    <p className="mt-3 text-xs font-semibold text-red-700">
                      {event.error_message ? 'View error reason' : 'View details'}
                    </p>
                  </div>
                ))}
                {(accuracy?.errors || []).length === 0 && <Empty />}
              </div>
            </ScrollArea>
          </Panel>
        </section>

        <section className="mt-6">
          <Panel title="Recent Query Events" subtitle="Latest tracked requests across the selected source.">
            <ScrollArea tall>
              <div className="space-y-3">
                {(questions?.recent_events || []).map((event) => (
                  <div key={event.id} className="rounded-lg border border-slate-200 p-4">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <span>{event.created_at ? new Date(event.created_at).toLocaleString() : ''}</span>
                      <span className="rounded-full bg-slate-100 px-2 py-1 font-medium text-slate-700">{event.source}</span>
                      <span className="rounded-full bg-cyan-50 px-2 py-1 font-medium text-cyan-700">
                        {event.question_analysis?.intent_category || 'pending intent'}
                      </span>
                      <span className={outcomeClassName(event.evaluation?.outcome)}>
                        {event.evaluation?.outcome || 'pending outcome'}
                      </span>
                      <span className="ml-auto tabular-nums">{formatMs(event.latency_ms)}</span>
                    </div>
                    <p className="mt-3 text-sm font-medium text-slate-900">{event.user_message}</p>
                    {event.bot_response_preview && (
                      <MarkdownAnswer compact>{event.bot_response_preview}</MarkdownAnswer>
                    )}
                  </div>
                ))}
              </div>
              {(questions?.recent_events || []).length === 0 && <Empty />}
            </ScrollArea>
          </Panel>
        </section>
      </main>

      {reviewSession && (
        <ReviewModal
          session={reviewSession}
          onSelect={(outcome) => {
            setReviewActionError(null);
            updateCurrentReviewItem({ selectedOutcome: outcome });
          }}
          onApply={() => {
            const currentItem = reviewSession.items[reviewSession.index];
            applyCurrentReview(
              currentItem.selectedOutcome || currentItem.review.classification,
              currentItem.selectedOutcome ? 'user_override' : 'llm_accept',
            );
          }}
          onSkip={skipCurrentReview}
          onBack={goBackReview}
          onClose={closeReviewModal}
          error={reviewActionError}
          saving={savingReview}
        />
      )}
      {selectedCluster && (
        <ClusterModal
          cluster={selectedCluster}
          onClose={() => setSelectedCluster(null)}
        />
      )}
      {selectedError && (
        <ErrorDetailModal
          event={selectedError}
          onClose={() => setSelectedError(null)}
        />
      )}
      {showLatencyDetails && (
        <LatencyDetailsModal
          distribution={latencyDistribution}
          days={days}
          source={source}
          onClose={() => setShowLatencyDetails(false)}
        />
      )}
    </div>
  );
};

const Panel = ({ title, subtitle, action, children }) => (
  <section className="rounded-lg border border-slate-200 bg-white p-5">
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
    {children}
  </section>
);

const ScrollArea = ({ children, compact = false, tall = false }) => {
  const height = tall ? 'max-h-[560px]' : compact ? 'max-h-[260px]' : 'max-h-[360px]';
  return (
    <div className={`${height} overflow-y-auto pr-2`}>
      {children}
    </div>
  );
};

const Empty = () => (
  <div className="rounded-lg border border-dashed border-slate-300 p-6 text-sm text-slate-500">
    No processed analytics yet. Run the worker to populate this view.
  </div>
);

const HUMAN_REVIEW_OUTCOMES = ['correct', 'incorrect'];

const ErrorDetailModal = ({ event, onClose }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-6">
    <div className="max-h-full w-full max-w-3xl overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-xl">
      <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-5">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Error Details</h2>
          <p className="mt-1 text-sm text-slate-500">
            {event.created_at ? new Date(event.created_at).toLocaleString() : 'Unknown time'}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
        >
          Close
        </button>
      </div>

      <div className="space-y-5 p-5">
        <div className="flex flex-wrap gap-2 text-xs">
          <span className={attentionOutcomePillClass}>{event.outcome || 'error'}</span>
          <span className="rounded-full bg-slate-100 px-2 py-1 font-medium text-slate-700">{event.source || 'unknown source'}</span>
          {event.error_type && (
            <span className="rounded-full bg-red-50 px-2 py-1 font-medium text-red-700">{event.error_type}</span>
          )}
          <span className="rounded-full bg-slate-100 px-2 py-1 font-medium text-slate-700">{formatMs(event.latency_ms)}</span>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Question</p>
          <p className="mt-2 text-sm font-medium text-slate-900">{event.user_message}</p>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Reason</p>
          <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-red-100 bg-red-50 p-4 text-sm leading-6 text-red-900">{event.error_message || 'No error message was captured for this event.'}</pre>
        </div>

        {event.bot_response_preview && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Response Preview</p>
            <MarkdownAnswer>{event.bot_response_preview}</MarkdownAnswer>
          </div>
        )}
      </div>
    </div>
  </div>
);

const LatencyDetailsModal = ({ distribution, days, source, onClose }) => {
  const sourceLabel = SOURCES.find((item) => item.value === source)?.label || source || 'All sources';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-6">
      <div className="max-h-full w-full max-w-3xl overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-5">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Latency Details</h2>
            <p className="mt-1 text-sm text-slate-500">
              Last {days} days, {sourceLabel.toLowerCase()}. Error outcomes are excluded.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
        </div>

        <div className="space-y-5 p-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <MetricTile label="Samples" value={formatNumber(distribution?.count)} detail="Non-error events" />
            <MetricTile label="Median" value={formatMs(distribution?.p50)} detail="P50 latency" />
            <MetricTile label="P99" value={formatMs(distribution?.p99)} detail="Tail latency" />
          </div>
          <LatencyBoxPlot distribution={distribution} />
        </div>
      </div>
    </div>
  );
};

const LatencyBoxPlot = ({ distribution }) => {
  const count = Number(distribution?.count) || 0;
  if (!count) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-6 text-sm text-slate-500">
        No non-error latency samples yet.
      </div>
    );
  }

  const width = 760;
  const height = 250;
  const padding = 52;
  const plotRight = 560;
  const axisY = 132;
  const boxHeight = 46;
  const min = Number(distribution.min_ms) || 0;
  const max = Math.max(Number(distribution.max_ms) || 0, min + 1);
  const scale = (value) => padding + ((Number(value) - min) / (max - min)) * (plotRight - padding);
  const markers = [
    { key: 'p25', label: 'P25', value: distribution.p25, y: 58, color: '#0891b2' },
    { key: 'p50', label: 'P50', value: distribution.p50, y: 88, color: '#0f172a' },
    { key: 'p75', label: 'P75', value: distribution.p75, y: 118, color: '#0891b2' },
    { key: 'p95', label: 'P95', value: distribution.p95, y: 148, color: '#f59e0b' },
    { key: 'p99', label: 'P99', value: distribution.p99, y: 178, color: '#dc2626' },
  ];

  return (
    <div className="rounded-lg border border-slate-200 p-4">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Latency box plot" className="h-72 w-full">
        <line x1={scale(min)} y1={axisY} x2={scale(max)} y2={axisY} stroke="#94a3b8" strokeWidth="2" />
        <line x1={scale(min)} y1={axisY - 22} x2={scale(min)} y2={axisY + 22} stroke="#64748b" strokeWidth="2" />
        <line x1={scale(max)} y1={axisY - 22} x2={scale(max)} y2={axisY + 22} stroke="#64748b" strokeWidth="2" />
        <rect
          x={scale(distribution.p25)}
          y={axisY - boxHeight / 2}
          width={Math.max(scale(distribution.p75) - scale(distribution.p25), 2)}
          height={boxHeight}
          rx="4"
          fill="#e0f2fe"
          stroke="#0891b2"
          strokeWidth="2"
        />
        <line x1={scale(distribution.p50)} y1={axisY - 32} x2={scale(distribution.p50)} y2={axisY + 32} stroke="#0f172a" strokeWidth="3" />
        <line x1={scale(distribution.p95)} y1={axisY - 28} x2={scale(distribution.p95)} y2={axisY + 28} stroke="#f59e0b" strokeWidth="2" strokeDasharray="5 4" />
        <line x1={scale(distribution.p99)} y1={axisY - 34} x2={scale(distribution.p99)} y2={axisY + 34} stroke="#dc2626" strokeWidth="2" strokeDasharray="5 4" />

        {markers.map((marker) => (
          <g key={marker.key}>
            <circle cx={scale(marker.value)} cy={axisY} r="4" fill={marker.color} />
            <line x1={scale(marker.value)} y1={axisY} x2="606" y2={marker.y - 5} stroke="#cbd5e1" strokeWidth="1" />
            <circle cx="606" cy={marker.y - 5} r="3" fill={marker.color} />
            <text x="622" y={marker.y} className="fill-slate-900 text-[13px] font-semibold">
              {marker.label}
            </text>
            <text x="660" y={marker.y} className="fill-slate-500 text-[12px]">
              {formatMs(marker.value)}
            </text>
          </g>
        ))}

        <text x={scale(min)} y={axisY + 66} textAnchor="middle" className="fill-slate-500 text-[12px]">
          min {formatMs(min)}
        </text>
        <text x={scale(max)} y={axisY + 66} textAnchor="middle" className="fill-slate-500 text-[12px]">
          max {formatMs(max)}
        </text>
      </svg>
    </div>
  );
};

const ClusterModal = ({ cluster, onClose }) => {
  const questions = cluster.questions || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-6">
      <div className="max-h-full w-full max-w-5xl overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-5">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">{cluster.label || 'cluster'}</h2>
            <p className="mt-1 text-sm text-slate-500">{cluster.representative_question}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            Close
          </button>
        </div>

        <div className="space-y-6 p-5">
          <div className="grid gap-3 md:grid-cols-4">
            <MetricTile label="Questions" value={formatNumber(cluster.query_count)} detail="Total in this cluster" />
            <MetricTile label="Accuracy" value={formatPct(cluster.accuracy_rate)} detail="Correct / verifiable" />
            <MetricTile label="Error rate" value={formatPct(cluster.error_rate)} detail="Errored outcomes" />
            <MetricTile label="Avg latency" value={formatMs(cluster.avg_latency_ms)} detail="Across cluster events" />
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
            <div className="rounded-lg border border-slate-200 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-slate-900">Demand Per Hour</h3>
                <span className="text-xs text-slate-500">{cluster.hourly_demand?.length || 0} active hours</span>
              </div>
              <LineChart data={cluster.hourly_demand || []} />
            </div>

            <div className="space-y-4">
              <BreakdownList title="Source" rows={cluster.source_breakdown || []} labelKey="source" />
              <BreakdownList title="Outcomes" rows={cluster.outcome_breakdown || []} labelKey="outcome" />
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-slate-900">Questions</h3>
            <div className="mt-3 max-h-[360px] space-y-3 overflow-y-auto pr-2">
              {questions.map((item) => (
                <div key={item.id} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span>{item.created_at ? new Date(item.created_at).toLocaleString() : ''}</span>
                    <span className="rounded-full bg-slate-100 px-2 py-1 font-medium text-slate-700">{item.source}</span>
                    <span className={outcomeClassName(item.outcome)}>{item.outcome}</span>
                    <span className="ml-auto tabular-nums">{formatMs(item.latency_ms)}</span>
                  </div>
                  <p className="mt-2 text-sm font-medium text-slate-900">{item.question}</p>
                </div>
              ))}
              {questions.length === 0 && <Empty />}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const BreakdownList = ({ title, rows, labelKey }) => (
  <div className="rounded-lg border border-slate-200 p-4">
    <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
    <div className="mt-3 space-y-2">
      {rows.length === 0 ? (
        <p className="text-sm text-slate-500">No data yet</p>
      ) : (
        rows.map((row) => (
          <div key={row[labelKey]} className="flex items-center justify-between gap-3 text-sm">
            <span className="truncate text-slate-700">{row[labelKey] || 'unknown'}</span>
            <span className="tabular-nums text-slate-500">{formatNumber(row.query_count)}</span>
          </div>
        ))
      )}
    </div>
  </div>
);

const LineChart = ({ data }) => {
  const rows = data || [];
  const width = 640;
  const height = 180;
  const padding = 24;
  const max = Math.max(...rows.map((row) => Number(row.query_count) || 0), 1);
  const points = rows.map((row, index) => {
    const x = rows.length <= 1
      ? width / 2
      : padding + (index / (rows.length - 1)) * (width - padding * 2);
    const y = height - padding - ((Number(row.query_count) || 0) / max) * (height - padding * 2);
    return { ...row, x, y };
  });
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');

  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-6 text-sm text-slate-500">
        No hourly demand yet
      </div>
    );
  }

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Cluster demand per hour" className="h-48 w-full">
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#cbd5e1" />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="#cbd5e1" />
        <path d={path} fill="none" stroke="#0891b2" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((point) => (
          <circle key={`${point.hour}-${point.query_count}`} cx={point.x} cy={point.y} r="4" fill="#0891b2">
            <title>{`${new Date(point.hour).toLocaleString()}: ${point.query_count}`}</title>
          </circle>
        ))}
      </svg>
      <div className="flex justify-between gap-3 text-xs text-slate-500">
        <span>{rows[0]?.hour ? new Date(rows[0].hour).toLocaleString() : ''}</span>
        <span>{rows[rows.length - 1]?.hour ? new Date(rows[rows.length - 1].hour).toLocaleString() : ''}</span>
      </div>
    </div>
  );
};

const ReviewModal = ({ session, onSelect, onApply, onSkip, onBack, onClose, error, saving }) => {
  const currentItem = session.items[session.index];
  const { event, review, selectedOutcome, status } = currentItem;
  const classification = review?.classification || 'ambiguous';
  const effectiveOutcome = selectedOutcome || classification;
  const needsDecision = classification === 'ambiguous' && !selectedOutcome;
  const isBulk = session.mode === 'bulk';
  const alreadyApplied = status === 'applied';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-6">
      <div className="max-h-full w-full max-w-2xl overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 p-5">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Automatic Review</h2>
            <p className="mt-1 text-sm text-slate-500">
              {isBulk ? `Question ${session.index + 1} of ${session.items.length}` : 'Review the LLM classification before updating correctness.'}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Close
          </button>
        </div>

        <div className="space-y-5 p-5">
          <div>
            <span className="rounded-full bg-cyan-50 px-2 py-1 text-xs font-semibold text-cyan-700">
              LLM: {classification}
            </span>
            <span className="ml-2 rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
              confidence: {review?.confidence || 'unknown'}
            </span>
          </div>

          <div className="rounded-lg border border-slate-200 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Question</p>
            <p className="mt-2 text-sm text-slate-900">{event.user_message}</p>
            <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Answer</p>
            <MarkdownAnswer>{event.bot_response || event.bot_response_preview || 'No answer captured.'}</MarkdownAnswer>
          </div>

          <div>
            <p className="text-sm font-semibold text-slate-900">Rationale</p>
            <p className="mt-2 text-sm text-slate-600">{review?.rationale || 'No rationale returned.'}</p>
          </div>

          <div>
            <p className="text-sm font-semibold text-slate-900">Final classification</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {HUMAN_REVIEW_OUTCOMES.map((outcome) => (
                <button
                  key={outcome}
                  type="button"
                  onClick={() => onSelect(outcome)}
                  disabled={saving || alreadyApplied}
                  className={`rounded-md border px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60 ${
                    effectiveOutcome === outcome
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {outcome}
                </button>
              ))}
            </div>
            {classification === 'correct' && !selectedOutcome && (
              <p className="mt-2 text-xs text-slate-500">
                {isBulk ? 'Apply will mark this correct unless you choose an override.' : 'Closing without a selection will mark this correct.'}
              </p>
            )}
            {classification === 'incorrect' && !selectedOutcome && (
              <p className="mt-2 text-xs text-slate-500">
                This answer was an error, empty, or obvious non-answer.
              </p>
            )}
            {needsDecision && (
              <p className="mt-2 text-xs text-amber-700">Ambiguous classifications require a human correct/incorrect decision.</p>
            )}
            {alreadyApplied && (
              <p className="mt-2 text-xs text-emerald-700">Applied as {currentItem.appliedOutcome}.</p>
            )}
          </div>

          {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        </div>

        <div className="flex flex-wrap justify-end gap-3 border-t border-slate-200 p-5">
          <button
            type="button"
            onClick={isBulk ? onBack : onClose}
            disabled={saving || (isBulk && session.index === 0)}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isBulk ? 'Go Back' : 'Close'}
          </button>
          {isBulk && (
            <button
              type="button"
              onClick={onSkip}
              disabled={saving}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Skip
            </button>
          )}
          {isBulk && (
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Close
            </button>
          )}
          <button
            type="button"
            onClick={onApply}
            disabled={saving || needsDecision || alreadyApplied}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {saving ? 'Applying...' : `Apply ${effectiveOutcome}`}
          </button>
        </div>
      </div>
    </div>
  );
};

const MarkdownAnswer = ({ children, compact = false }) => (
  <div className={`markdown-content mt-2 text-sm text-slate-700 ${compact ? 'max-h-16 overflow-hidden' : ''}`}>
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ node, ...props }) => (
          <div className="my-3 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-300 border border-slate-300" {...props} />
          </div>
        ),
        th: ({ node, ...props }) => (
          <th className="border-r border-slate-300 px-3 py-2 text-left text-xs font-semibold uppercase text-slate-900 last:border-r-0" {...props} />
        ),
        td: ({ node, ...props }) => (
          <td className="border-r border-slate-200 px-3 py-2 text-sm text-slate-700 last:border-r-0" {...props} />
        ),
        h1: ({ node, ...props }) => <h1 className="mb-2 text-lg font-semibold text-slate-900" {...props} />,
        h2: ({ node, ...props }) => <h2 className="mb-2 text-base font-semibold text-slate-900" {...props} />,
        h3: ({ node, ...props }) => <h3 className="mb-2 text-sm font-semibold text-slate-900" {...props} />,
        p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
        ul: ({ node, ...props }) => <ul className="mb-2 list-inside list-disc space-y-1" {...props} />,
        ol: ({ node, ...props }) => <ol className="mb-2 list-inside list-decimal space-y-1" {...props} />,
        strong: ({ node, ...props }) => <strong className="font-semibold text-slate-900" {...props} />,
        em: ({ node, ...props }) => <em className="italic" {...props} />,
        code: ({ node, inline, ...props }) => (
          inline
            ? <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-sm" {...props} />
            : <code className="block overflow-x-auto rounded bg-slate-100 p-2 font-mono text-sm" {...props} />
        ),
      }}
    >
      {children}
    </ReactMarkdown>
  </div>
);

export default AnalyticsDashboard;
