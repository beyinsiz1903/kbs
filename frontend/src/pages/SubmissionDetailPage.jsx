import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';
import { getSubmission, requeueSubmission, correctSubmission, getHotels } from '../lib/api';
import { StatusBadge } from '../components/StatusBadge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import {
  ArrowLeft, Copy, Check, RotateCw, Pencil, Clock, Send, CheckCircle2,
  XCircle, AlertTriangle, ShieldAlert, RefreshCw
} from 'lucide-react';

const actionIcons = {
  checkin_created: CheckCircle2,
  submission_created: Send,
  validation_success: Check,
  validation_failed: XCircle,
  queued: Clock,
  sent_to_kbs: Send,
  kbs_ack: CheckCircle2,
  kbs_fail: XCircle,
  retry_scheduled: RefreshCw,
  quarantined: ShieldAlert,
  manual_correction: Pencil,
  requeued: RotateCw
};

const actionColors = {
  checkin_created: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  submission_created: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
  validation_success: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  validation_failed: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
  queued: 'text-slate-400 bg-slate-500/10 border-slate-500/20',
  sent_to_kbs: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
  kbs_ack: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  kbs_fail: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
  retry_scheduled: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  quarantined: 'text-fuchsia-400 bg-fuchsia-500/10 border-fuchsia-500/20',
  manual_correction: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  requeued: 'text-amber-400 bg-amber-500/10 border-amber-500/20'
};

export default function SubmissionDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { t } = useLanguage();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [copiedField, setCopiedField] = useState(null);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correction, setCorrection] = useState({});
  const [hotels, setHotels] = useState([]);

  const fetchData = async () => {
    try {
      const [d, h] = await Promise.all([getSubmission(id), getHotels()]);
      setData(d);
      setHotels(h);
    } catch (err) {
      console.error(err);
      toast.error('Failed to load submission');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [id]);

  const copyToClipboard = async (text, field) => {
    await navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
    toast.success(t('detail.copied'));
  };

  const handleRequeue = async () => {
    try {
      await requeueSubmission(id);
      toast.success('Yeniden kuyruga eklendi / Requeued');
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    }
  };

  const handleCorrection = async () => {
    try {
      await correctSubmission(id, correction);
      toast.success('Duzeltme uygulandi / Correction applied');
      setCorrectionOpen(false);
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!data?.submission) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">Submission not found</p>
        <Button variant="outline" className="mt-4" onClick={() => navigate('/submissions')}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back
        </Button>
      </div>
    );
  }

  const sub = data.submission;
  const attempts = data.attempts || [];
  const audit = data.audit_trail || [];
  const gd = sub.guest_data || {};
  const hotel = hotels.find(h => h.id === sub.hotel_id);

  return (
    <div className="space-y-6" data-testid="submission-detail-page">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/submissions')} data-testid="back-button">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight">{t('detail.title')}</h1>
              <StatusBadge status={sub.status} />
            </div>
            <p className="text-xs font-mono text-muted-foreground mt-0.5">{sub.id}</p>
          </div>
        </div>
        <div className="flex gap-2">
          {sub.status === 'quarantined' && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setCorrection({
                    first_name: gd.first_name || '',
                    last_name: gd.last_name || '',
                    tc_kimlik_no: gd.tc_kimlik_no || '',
                    passport_no: gd.passport_no || '',
                    nationality: gd.nationality || '',
                    passport_country: gd.passport_country || '',
                  });
                  setCorrectionOpen(true);
                }}
                data-testid="submission-correct-button"
              >
                <Pencil className="h-3.5 w-3.5 mr-1.5" /> {t('submissions.correct')}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRequeue}
                data-testid="submission-requeue-button"
              >
                <RotateCw className="h-3.5 w-3.5 mr-1.5" /> {t('submissions.requeue')}
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left: Timeline + Audit */}
        <div className="space-y-6">
          {/* Guest Data */}
          <Card className="bg-card/60 border-border/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-muted-foreground">{t('detail.guestData')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-2 text-sm">
                {gd.first_name && (
                  <div className="flex justify-between"><span className="text-muted-foreground">{t('checkin.firstName')}</span><span className="font-medium">{gd.first_name}</span></div>
                )}
                {gd.last_name && (
                  <div className="flex justify-between"><span className="text-muted-foreground">{t('checkin.lastName')}</span><span className="font-medium">{gd.last_name}</span></div>
                )}
                {gd.tc_kimlik_no && (
                  <div className="flex justify-between"><span className="text-muted-foreground">{t('checkin.tcKimlik')}</span><span className="font-mono">{gd.tc_kimlik_no}</span></div>
                )}
                {gd.passport_no && (
                  <div className="flex justify-between"><span className="text-muted-foreground">{t('checkin.passportNo')}</span><span className="font-mono">{gd.passport_no}</span></div>
                )}
                {gd.nationality && (
                  <div className="flex justify-between"><span className="text-muted-foreground">{t('checkin.nationality')}</span><span>{gd.nationality}</span></div>
                )}
                {gd.room_number && (
                  <div className="flex justify-between"><span className="text-muted-foreground">{t('checkin.roomNumber')}</span><span className="font-mono">{gd.room_number}</span></div>
                )}
                {hotel && (
                  <div className="flex justify-between"><span className="text-muted-foreground">{t('checkin.hotel')}</span><span>{hotel.name}</span></div>
                )}
                {sub.kbs_reference_id && (
                  <div className="flex justify-between"><span className="text-muted-foreground">KBS Ref</span><span className="font-mono text-primary">{sub.kbs_reference_id}</span></div>
                )}
                {sub.quarantine_reason && (
                  <div className="mt-2 rounded-lg bg-rose-500/10 border border-rose-500/20 p-3">
                    <p className="text-xs font-medium text-rose-300"><AlertTriangle className="h-3.5 w-3.5 inline mr-1" /> {sub.quarantine_reason}</p>
                    {sub.last_error && <p className="text-xs text-rose-300/70 mt-1">{sub.last_error}</p>}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Timeline */}
          <Card className="bg-card/60 border-border/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-muted-foreground">{t('detail.timeline')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-0">
                {audit.length === 0 ? (
                  <p className="text-sm text-muted-foreground py-4 text-center">{t('detail.noAttempts')}</p>
                ) : (
                  audit.map((event, i) => {
                    const IconComp = actionIcons[event.action] || Clock;
                    const colorClass = actionColors[event.action] || 'text-slate-400 bg-slate-500/10 border-slate-500/20';
                    return (
                      <motion.div
                        key={event.id || i}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.05 }}
                        className="flex gap-3 pb-4"
                      >
                        <div className="flex flex-col items-center">
                          <div className={`flex h-8 w-8 items-center justify-center rounded-full border ${colorClass}`}>
                            <IconComp className="h-3.5 w-3.5" />
                          </div>
                          {i < audit.length - 1 && <div className="flex-1 w-px bg-border/30 mt-1" />}
                        </div>
                        <div className="flex-1 min-w-0 pt-0.5">
                          <p className="text-sm font-medium">{event.action?.replace(/_/g, ' ')}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {event.created_at ? new Date(event.created_at).toLocaleString() : ''}
                          </p>
                          {event.details && Object.keys(event.details).length > 0 && (
                            <div className="mt-1 text-xs text-muted-foreground/70 font-mono bg-muted/20 rounded px-2 py-1">
                              {JSON.stringify(event.details, null, 0).slice(0, 200)}
                            </div>
                          )}
                        </div>
                      </motion.div>
                    );
                  })
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: XML Viewers + Attempts */}
        <div className="space-y-6">
          {/* Attempts */}
          {attempts.length > 0 && attempts.map((att, i) => (
            <Card key={att.id || i} className="bg-card/60 border-border/50">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">
                    {t('detail.attemptNumber')} #{att.attempt_number}
                    <span className={`ml-2 text-xs ${att.status === 'success' ? 'text-emerald-400' : 'text-rose-400'}`}>
                      ({att.status})
                    </span>
                  </CardTitle>
                  <span className="text-xs text-muted-foreground">
                    {att.duration_ms}ms
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {att.error_code && (
                  <div className="rounded-lg bg-rose-500/10 border border-rose-500/20 p-2">
                    <p className="text-xs text-rose-300 font-mono">{att.error_code}: {att.error_message}</p>
                  </div>
                )}

                {/* Request XML */}
                {att.request_xml && (
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <p className="text-xs font-medium text-muted-foreground">{t('detail.requestXml')}</p>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs"
                        onClick={() => copyToClipboard(att.request_xml, `req-${i}`)}
                        data-testid="submission-detail-xml-copy-button"
                      >
                        {copiedField === `req-${i}` ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                        {copiedField === `req-${i}` ? t('detail.copied') : t('detail.copyXml')}
                      </Button>
                    </div>
                    <ScrollArea className="h-[200px] rounded-lg border border-border/30 bg-background/40">
                      <pre className="p-3 text-xs leading-5 font-mono text-foreground/90 whitespace-pre-wrap">
                        {att.request_xml}
                      </pre>
                    </ScrollArea>
                  </div>
                )}

                {/* Response XML */}
                {att.response_xml && (
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <p className="text-xs font-medium text-muted-foreground">{t('detail.responseXml')}</p>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs"
                        onClick={() => copyToClipboard(att.response_xml, `res-${i}`)}
                      >
                        {copiedField === `res-${i}` ? <Check className="h-3 w-3 mr-1" /> : <Copy className="h-3 w-3 mr-1" />}
                        {copiedField === `res-${i}` ? t('detail.copied') : t('detail.copyXml')}
                      </Button>
                    </div>
                    <ScrollArea className="h-[200px] rounded-lg border border-border/30 bg-background/40">
                      <pre className="p-3 text-xs leading-5 font-mono text-foreground/90 whitespace-pre-wrap">
                        {att.response_xml}
                      </pre>
                    </ScrollArea>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}

          {attempts.length === 0 && (
            <Card className="bg-card/60 border-border/50">
              <CardContent className="py-12 text-center">
                <Clock className="h-8 w-8 mx-auto text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">{t('detail.noAttempts')}</p>
              </CardContent>
            </Card>
          )}

          {/* Metadata */}
          <Card className="bg-card/60 border-border/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm text-muted-foreground">{t('detail.metadata')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-2 text-xs">
                <div className="flex justify-between"><span className="text-muted-foreground">ID</span><span className="font-mono">{sub.id}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Idempotency Key</span><span className="font-mono text-right truncate ml-4">{sub.idempotency_key}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Fingerprint</span><span className="font-mono text-right truncate ml-4">{sub.fingerprint?.slice(0, 16)}...</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">{t('submissions.attempts')}</span><span className="font-mono">{sub.attempt_count}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Max Retries</span><span className="font-mono">{sub.max_retries}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">{t('submissions.created')}</span><span>{sub.created_at ? new Date(sub.created_at).toLocaleString() : '-'}</span></div>
                {sub.completed_at && (
                  <div className="flex justify-between"><span className="text-muted-foreground">Completed</span><span>{new Date(sub.completed_at).toLocaleString()}</span></div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Correction Dialog */}
      <Dialog open={correctionOpen} onOpenChange={setCorrectionOpen}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>{t('submissions.correct')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label>{t('checkin.firstName')}</Label>
                <Input
                  value={correction.first_name || ''}
                  onChange={e => setCorrection(p => ({ ...p, first_name: e.target.value }))}
                  className="mt-1"
                  data-testid="correction-firstname-input"
                />
              </div>
              <div>
                <Label>{t('checkin.lastName')}</Label>
                <Input
                  value={correction.last_name || ''}
                  onChange={e => setCorrection(p => ({ ...p, last_name: e.target.value }))}
                  className="mt-1"
                  data-testid="correction-lastname-input"
                />
              </div>
              {gd.tc_kimlik_no !== undefined && (
                <div>
                  <Label>{t('checkin.tcKimlik')}</Label>
                  <Input
                    value={correction.tc_kimlik_no || ''}
                    onChange={e => setCorrection(p => ({ ...p, tc_kimlik_no: e.target.value }))}
                    className="mt-1 font-mono"
                    data-testid="correction-tc-input"
                  />
                </div>
              )}
              {gd.passport_no !== undefined && (
                <>
                  <div>
                    <Label>{t('checkin.passportNo')}</Label>
                    <Input
                      value={correction.passport_no || ''}
                      onChange={e => setCorrection(p => ({ ...p, passport_no: e.target.value }))}
                      className="mt-1 font-mono"
                      data-testid="correction-passport-input"
                    />
                  </div>
                  <div>
                    <Label>{t('checkin.nationality')}</Label>
                    <Input
                      value={correction.nationality || ''}
                      onChange={e => setCorrection(p => ({ ...p, nationality: e.target.value }))}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label>{t('checkin.passportCountry')}</Label>
                    <Input
                      value={correction.passport_country || ''}
                      onChange={e => setCorrection(p => ({ ...p, passport_country: e.target.value }))}
                      className="mt-1 font-mono"
                    />
                  </div>
                </>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCorrectionOpen(false)}>{t('common.cancel')}</Button>
            <Button onClick={handleCorrection} data-testid="correction-submit-button">{t('common.save')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
