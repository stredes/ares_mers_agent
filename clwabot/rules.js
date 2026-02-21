// clwabot/rules.js
// Reglas centrales del agente Ares / clwabot

module.exports = {
  owner: {
    msisdn: "+56954764325",
  },
  vip: {
    msisdn: "+56975551112",
  },
  agent: {
    initialState: "INACTIVO", // INACTIVO | ACTIVO (para futuros modos)
  },
  commands: {
    ownerOnly: ["/agente on", "/agente off", "/agente status"],
  },
  allowedTargets: ["owner", "vip", "external"],
  external: {
    enabled: true,
    meeting: {
      triggerWords: ["reunion", "agendar", "meeting", "llamada", "cita"],
      graceSeconds: 15,
    },
  },
  urgency: {
    keywords: ["urgente", "urgencia"],
  },
};
