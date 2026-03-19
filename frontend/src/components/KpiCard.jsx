import React from 'react';
import { Card, CardContent } from './ui/card';
import { motion } from 'framer-motion';

export function KpiCard({ title, value, subtitle, icon: Icon, trend, className = '' }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card className={`bg-card/60 backdrop-blur border-border/50 ${className}`}>
        <CardContent className="p-5">
          <div className="flex items-start justify-between">
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{title}</p>
              <p className="text-3xl font-semibold tabular-nums tracking-tight">{value}</p>
              {subtitle && (
                <p className="text-xs text-muted-foreground">{subtitle}</p>
              )}
            </div>
            {Icon && (
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/5 border border-primary/10">
                <Icon className="h-5 w-5 text-primary/70" />
              </div>
            )}
          </div>
          {trend !== undefined && (
            <div className={`mt-2 text-xs font-medium ${
              trend >= 0 ? 'text-emerald-400' : 'text-rose-400'
            }`}>
              {trend >= 0 ? '+' : ''}{trend}%
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
