export interface AppMetricsConfig {
  hero: {
    taglineLatencyMs: number;
    throughputDisplay: string;
    precisionPct: number;
    recallPct: number;
    medianLatencyMs: number;
  };
  statCards: {
    capitalProtectedK: number;
    transactionsPerDayM: number;
    fraudIncidenceRatePct: number;
    streamLagSeconds: number;
  };
  pipeline: {
    stages: Array<{ ic: string; name: string; tech: string; stat: string }>;
  };
  trace: {
    normalAmountUsd: string;
    normalFraudProb: string;
    fraudAmountUsd: string;
    fraudDistanceKm: string;
    fraudProbability: string;
    kafkaTimingMs: number;
    featureTimingMs: number;
    verdictTimingMs: number;
    responseTimingMs: number;
    featureDimensions: number;
    geoOutlierCount: number;
  };
  dashboard: {
    defaultTotalTransactions: number;
    defaultFraudDetected: number;
    defaultFraudRatePct: number;
    defaultModelAccuracyPct: number;
    displayRecallPct: number;
    fraudRateDeltaLabel: string;
  };
  architecture: {
    kafkaThroughput: string;
    sparkBatchInterval: string;
    endToEndLatency: string;
    modelAccuracyDisplay: string;
  };
  cta: {
    setupMinutes: number;
  };
  chat: {
    highValueFraudThreshold: number;
  };
  caseDetail: {
    transactionId: string;
    caseId: string;
    fraudConfidencePct: number;
    fraudAmountDisplay: string;
    fraudAmountFull: string;
    fraudModelProbDisplay: string;
    verdictLatencyMs: number;
    totalFeatures: number;
    cardLast4: string;
    cardIssuedYear: number;
    cardAgeYears: number;
    cardholderName: string;
    cardholderCity: string;
    cardholderAvgTicketFull: string;
    cardholderAvgTicketShort: string;
    cardholderTenureYears: number;
    cardholderTotalSwipes: number;
    distanceFromHomeKm: string;
    velocityDescription: string;
    merchantRiskScore: number;
    amountVsAvgMultiplier: string;
    analystName: string;
  };
}

export const APP_METRICS: AppMetricsConfig = {
  hero: {
    taglineLatencyMs:  38,
    throughputDisplay: '23.4K',
    precisionPct:      94.3,
    recallPct:         92.0,
    medianLatencyMs:   38,
  },

  statCards: {
    capitalProtectedK:     184,
    transactionsPerDayM:   2.4,
    fraudIncidenceRatePct: 0.42,
    streamLagSeconds:      4.2,
  },

  pipeline: {
    stages: [
      { ic: '↘', name: 'Ingest',    tech: 'Kafka',           stat: '23.4K msg/s'   },
      { ic: '∿', name: 'Stream',    tech: 'Redpanda Cloud',  stat: '2.0s batch'    },
      { ic: '▦', name: 'Featurise', tech: 'Feature store',   stat: '8 ms lookup'   },
      { ic: '◈', name: 'Score',     tech: 'RF v1.2 · CAPE', stat: '38 ms verdict' },
      { ic: '→', name: 'Decide',    tech: 'Decision API',    stat: '<100ms total'  },
    ],
  },

  trace: {
    normalAmountUsd:   '$42.18',
    normalFraudProb:   'p=0.02',
    fraudAmountUsd:    '$487',
    fraudDistanceKm:   '1,847 km',
    fraudProbability:  'p=0.98',
    kafkaTimingMs:     12,
    featureTimingMs:   22,
    verdictTimingMs:   38,
    responseTimingMs:  44,
    featureDimensions: 38,
    geoOutlierCount:   4,
  },

  dashboard: {
    defaultTotalTransactions: 23400,
    defaultFraudDetected:     47,
    defaultFraudRatePct:      0.42,
    defaultModelAccuracyPct:  94.3,
    displayRecallPct:         92.0,
    fraudRateDeltaLabel:      '+0.08 pp · vs prior 60-min window',
  },

  architecture: {
    kafkaThroughput:      '23K msg/s',
    sparkBatchInterval:   '2s',
    endToEndLatency:      '<20s',
    modelAccuracyDisplay: '94.35%',
  },

  cta: {
    setupMinutes: 20,
  },

  chat: {
    highValueFraudThreshold: 500,
  },

  caseDetail: {
    transactionId:            'TX-49281',
    caseId:                   'C-7714',
    fraudConfidencePct:       98.2,
    fraudAmountDisplay:       '$487',
    fraudAmountFull:          '$487.20',
    fraudModelProbDisplay:    'p=0.982',
    verdictLatencyMs:         38,
    totalFeatures:            38,
    cardLast4:                '4821',
    cardIssuedYear:           2021,
    cardAgeYears:             4.2,
    cardholderName:           'M. Chen',
    cardholderCity:           'Seattle, WA',
    cardholderAvgTicketFull:  '$42.18',
    cardholderAvgTicketShort: '$42',
    cardholderTenureYears:    7,
    cardholderTotalSwipes:    3420,
    distanceFromHomeKm:       '1,847 km',
    velocityDescription:      '5 swipes / 23 min',
    merchantRiskScore:        0.73,
    amountVsAvgMultiplier:    '11.6×',
    analystName:              'S. Marlowe',
  },
};
