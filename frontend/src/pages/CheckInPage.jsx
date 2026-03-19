import React, { useState, useEffect } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { getHotels, createGuest, createCheckIn } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { UserPlus, Send, CheckCircle2, Building2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function CheckInPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [hotels, setHotels] = useState([]);
  const [guestType, setGuestType] = useState('tc_citizen');
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    hotel_id: '',
    tc_kimlik_no: '',
    first_name: '',
    last_name: '',
    birth_date: '',
    passport_no: '',
    nationality: '',
    passport_country: '',
    passport_expiry: '',
    phone: '',
    email: '',
    room_number: '',
    check_in_date: new Date().toISOString().split('T')[0],
    check_out_date: '',
    number_of_guests: 1
  });

  useEffect(() => {
    getHotels().then(setHotels).catch(console.error);
  }, []);

  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.hotel_id) {
      toast.error(t('checkin.selectHotel'));
      return;
    }
    setSubmitting(true);
    try {
      // Create guest first
      const guestData = {
        hotel_id: form.hotel_id,
        guest_type: guestType,
        first_name: form.first_name,
        last_name: form.last_name,
        birth_date: form.birth_date || undefined,
        phone: form.phone || undefined,
        email: form.email || undefined
      };
      if (guestType === 'tc_citizen') {
        guestData.tc_kimlik_no = form.tc_kimlik_no;
      } else {
        guestData.passport_no = form.passport_no;
        guestData.nationality = form.nationality;
        guestData.passport_country = form.passport_country;
        guestData.passport_expiry = form.passport_expiry || undefined;
      }

      const guest = await createGuest(guestData);

      // Create check-in
      const checkinData = {
        hotel_id: form.hotel_id,
        guest_id: guest.id,
        room_number: form.room_number,
        check_in_date: form.check_in_date,
        check_out_date: form.check_out_date || undefined,
        number_of_guests: parseInt(form.number_of_guests) || 1
      };

      const result = await createCheckIn(checkinData);

      if (result.duplicate) {
        toast.warning('Mukerrer bildirim / Duplicate submission detected');
      } else {
        toast.success(t('checkin.success'));
      }

      // Reset form
      setForm(prev => ({
        ...prev,
        tc_kimlik_no: '', first_name: '', last_name: '', birth_date: '',
        passport_no: '', nationality: '', passport_country: '', passport_expiry: '',
        phone: '', email: '', room_number: '', number_of_guests: 1,
        check_out_date: ''
      }));

    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      toast.error(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="checkin-page">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{t('checkin.title')}</h1>
        <p className="text-muted-foreground mt-1">{t('checkin.subtitle')}</p>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Main Form */}
          <div className="lg:col-span-2 space-y-6">
            {/* Hotel Select */}
            <Card className="bg-card/60 border-border/50">
              <CardHeader className="pb-4">
                <CardTitle className="text-base flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-primary" />
                  {t('checkin.hotel')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Select value={form.hotel_id} onValueChange={(v) => handleChange('hotel_id', v)}>
                  <SelectTrigger data-testid="checkin-hotel-select">
                    <SelectValue placeholder={t('checkin.selectHotel')} />
                  </SelectTrigger>
                  <SelectContent>
                    {hotels.map(h => (
                      <SelectItem key={h.id} value={h.id}>{h.name} - {h.city}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>

            {/* Guest Identity */}
            <Card className="bg-card/60 border-border/50">
              <CardHeader className="pb-4">
                <CardTitle className="text-base flex items-center gap-2">
                  <UserPlus className="h-4 w-4 text-primary" />
                  {t('checkin.guestType')}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Tabs value={guestType} onValueChange={setGuestType}>
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="tc_citizen" data-testid="checkin-type-tc">
                      {t('checkin.tcCitizen')}
                    </TabsTrigger>
                    <TabsTrigger value="foreign" data-testid="checkin-type-foreign">
                      {t('checkin.foreign')}
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="tc_citizen" className="space-y-4 mt-4">
                    <div>
                      <Label>{t('checkin.tcKimlik')} *</Label>
                      <Input
                        value={form.tc_kimlik_no}
                        onChange={e => handleChange('tc_kimlik_no', e.target.value)}
                        placeholder="10000000146"
                        maxLength={11}
                        className="mt-1.5 font-mono"
                        data-testid="checkin-tc-input"
                        required={guestType === 'tc_citizen'}
                      />
                    </div>
                  </TabsContent>

                  <TabsContent value="foreign" className="space-y-4 mt-4">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <Label>{t('checkin.passportNo')} *</Label>
                        <Input
                          value={form.passport_no}
                          onChange={e => handleChange('passport_no', e.target.value)}
                          placeholder="AB123456"
                          className="mt-1.5 font-mono"
                          data-testid="checkin-passport-input"
                          required={guestType === 'foreign'}
                        />
                      </div>
                      <div>
                        <Label>{t('checkin.nationality')} *</Label>
                        <Input
                          value={form.nationality}
                          onChange={e => handleChange('nationality', e.target.value)}
                          placeholder="American"
                          className="mt-1.5"
                          data-testid="checkin-nationality-input"
                          required={guestType === 'foreign'}
                        />
                      </div>
                      <div>
                        <Label>{t('checkin.passportCountry')} *</Label>
                        <Input
                          value={form.passport_country}
                          onChange={e => handleChange('passport_country', e.target.value)}
                          placeholder="US"
                          maxLength={3}
                          className="mt-1.5 font-mono"
                          data-testid="checkin-passport-country-input"
                          required={guestType === 'foreign'}
                        />
                      </div>
                      <div>
                        <Label>{t('checkin.passportExpiry')}</Label>
                        <Input
                          type="date"
                          value={form.passport_expiry}
                          onChange={e => handleChange('passport_expiry', e.target.value)}
                          className="mt-1.5"
                          data-testid="checkin-passport-expiry-input"
                        />
                      </div>
                    </div>
                  </TabsContent>
                </Tabs>

                {/* Common name fields */}
                <div className="grid gap-4 md:grid-cols-2 pt-2">
                  <div>
                    <Label>{t('checkin.firstName')} *</Label>
                    <Input
                      value={form.first_name}
                      onChange={e => handleChange('first_name', e.target.value)}
                      className="mt-1.5"
                      data-testid="checkin-firstname-input"
                      required
                    />
                  </div>
                  <div>
                    <Label>{t('checkin.lastName')} *</Label>
                    <Input
                      value={form.last_name}
                      onChange={e => handleChange('last_name', e.target.value)}
                      className="mt-1.5"
                      data-testid="checkin-lastname-input"
                      required
                    />
                  </div>
                  <div>
                    <Label>{t('checkin.birthDate')}</Label>
                    <Input
                      type="date"
                      value={form.birth_date}
                      onChange={e => handleChange('birth_date', e.target.value)}
                      className="mt-1.5"
                      data-testid="checkin-birthdate-input"
                    />
                  </div>
                  <div>
                    <Label>{t('checkin.phone')}</Label>
                    <Input
                      value={form.phone}
                      onChange={e => handleChange('phone', e.target.value)}
                      placeholder="+905551234567"
                      className="mt-1.5"
                      data-testid="checkin-phone-input"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Stay Info */}
            <Card className="bg-card/60 border-border/50">
              <CardHeader className="pb-4">
                <CardTitle className="text-base flex items-center gap-2">
                  <Send className="h-4 w-4 text-primary" />
                  Konaklama Bilgileri
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <Label>{t('checkin.roomNumber')} *</Label>
                    <Input
                      value={form.room_number}
                      onChange={e => handleChange('room_number', e.target.value)}
                      placeholder="101"
                      className="mt-1.5 font-mono"
                      data-testid="checkin-room-input"
                      required
                    />
                  </div>
                  <div>
                    <Label>{t('checkin.numberOfGuests')}</Label>
                    <Input
                      type="number"
                      min="1"
                      value={form.number_of_guests}
                      onChange={e => handleChange('number_of_guests', e.target.value)}
                      className="mt-1.5"
                      data-testid="checkin-guests-input"
                    />
                  </div>
                  <div>
                    <Label>{t('checkin.checkInDate')} *</Label>
                    <Input
                      type="date"
                      value={form.check_in_date}
                      onChange={e => handleChange('check_in_date', e.target.value)}
                      className="mt-1.5"
                      data-testid="checkin-date-input"
                      required
                    />
                  </div>
                  <div>
                    <Label>{t('checkin.checkOutDate')}</Label>
                    <Input
                      type="date"
                      value={form.check_out_date}
                      onChange={e => handleChange('check_out_date', e.target.value)}
                      className="mt-1.5"
                      data-testid="checkin-checkout-input"
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Summary Panel */}
          <div className="space-y-4">
            <Card className="bg-card/60 border-border/50 sticky top-20">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Check-in Ozeti</CardTitle>
                <CardDescription>KBS bildirimi otomatik olusturulacak</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-lg bg-muted/30 p-3 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{t('checkin.guestType')}</span>
                    <span className="font-medium">{guestType === 'tc_citizen' ? t('checkin.tcCitizen') : t('checkin.foreign')}</span>
                  </div>
                  {form.first_name && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">{t('checkin.firstName')}</span>
                      <span className="font-medium">{form.first_name} {form.last_name}</span>
                    </div>
                  )}
                  {form.room_number && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">{t('checkin.roomNumber')}</span>
                      <span className="font-mono font-medium">{form.room_number}</span>
                    </div>
                  )}
                  {form.hotel_id && hotels.length > 0 && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">{t('checkin.hotel')}</span>
                      <span className="font-medium text-right truncate ml-2">{hotels.find(h => h.id === form.hotel_id)?.name || ''}</span>
                    </div>
                  )}
                </div>

                <Button
                  type="submit"
                  className="w-full"
                  disabled={submitting}
                  data-testid="checkin-submit-button"
                >
                  {submitting ? (
                    <><Send className="h-4 w-4 mr-2 animate-spin" /> {t('checkin.submitting')}</>
                  ) : (
                    <><CheckCircle2 className="h-4 w-4 mr-2" /> {t('checkin.submit')}</>
                  )}
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </form>
    </div>
  );
}
