"""Small hand-written knowledge base for development and tests.

These are NOT organizer data. IDs use the MOCK- prefix so they can never be confused
with the official TKT- ticket IDs from the 80/20 split.
"""

MOCK_HISTORICAL_TICKETS: list[dict[str, str]] = [
    {
        "ticket_id": "MOCK-0001",
        "subject": "VPN down for the entire hospital network",
        "body": "Since 8am none of our clinicians can connect through the VPN. "
        "Telemedicine sessions and the EMR integration fail at all sites.",
        "answer": "We found an expired certificate on the VPN gateway. Our on-call "
        "engineer renewed it and restarted the gateway service, and connections "
        "are restored. Please reconnect your VPN client and confirm access.",
        "type": "Incident",
        "queue": "Technical Support",
        "priority": "high",
        "language": "en",
    },
    {
        "ticket_id": "MOCK-0002",
        "subject": "Cannot connect to VPN after laptop update",
        "body": "After installing this week's operating system update, my VPN "
        "client fails with error 809.",
        "answer": "Error 809 after the update comes from the new firewall profile. "
        "Please reinstall the VPN client from the self-service portal and restart "
        "your laptop. If the error persists, reply with your client log.",
        "type": "Incident",
        "queue": "IT Support",
        "priority": "medium",
        "language": "en",
    },
    {
        "ticket_id": "MOCK-0003",
        "subject": "Password reset email never arrives",
        "body": "I forgot my password for the customer portal and the reset email "
        "never arrives.",
        "answer": "Please check your spam folder for the reset email. We have sent a "
        "new reset link, which is valid for 24 hours. If it still does not arrive, "
        "confirm the email address on your account.",
        "type": "Request",
        "queue": "Customer Service",
        "priority": "low",
        "language": "en",
    },
    {
        "ticket_id": "MOCK-0004",
        "subject": "Passwort zurücksetzen",
        "body": "Ich habe mein Passwort vergessen und kann mich nicht im "
        "Kundenportal anmelden.",
        "answer": "Bitte nutzen Sie die Funktion 'Passwort vergessen' auf der "
        "Anmeldeseite. Wir haben Ihnen einen neuen Link gesendet. Prüfen Sie bitte "
        "auch Ihren Spam-Ordner.",
        "type": "Request",
        "queue": "Customer Service",
        "priority": "low",
        "language": "de",
    },
    {
        "ticket_id": "MOCK-0005",
        "subject": "Charged twice for the March invoice",
        "body": "Our credit card was charged twice for the March invoice. "
        "Please fix this.",
        "answer": "We confirmed the duplicate charge and issued a refund for the "
        "second payment. Refunds appear on your statement within 5-7 business days.",
        "type": "Problem",
        "queue": "Billing and Payments",
        "priority": "medium",
        "language": "en",
    },
    {
        "ticket_id": "MOCK-0006",
        "subject": "Doppelte Abbuchung der Rechnung",
        "body": "Uns wurde die Rechnung für April doppelt abgebucht.",
        "answer": "Wir haben die doppelte Abbuchung bestätigt und die zweite Zahlung "
        "erstattet. Die Gutschrift erscheint innerhalb von 5 bis 7 Werktagen auf "
        "Ihrem Konto.",
        "type": "Problem",
        "queue": "Billing and Payments",
        "priority": "medium",
        "language": "de",
    },
    {
        "ticket_id": "MOCK-0007",
        "subject": "Does your analytics suite integrate with Salesforce?",
        "body": "We are evaluating your product. Is there a native Salesforce "
        "integration?",
        "answer": "Our analytics suite connects to Salesforce through the standard "
        "REST connector described in the integration guide. A sales engineer can "
        "schedule a demo for your team.",
        "type": "Request",
        "queue": "Sales and Pre-Sales",
        "priority": "low",
        "language": "en",
    },
    {
        "ticket_id": "MOCK-0008",
        "subject": "Suspicious logins and possible data breach",
        "body": "We see logins from unknown countries, and customer records were "
        "exported overnight.",
        "answer": "Our security team locked the affected accounts, revoked active "
        "sessions, and opened an incident investigation. Please reset all admin "
        "passwords and enable two-factor authentication.",
        "type": "Incident",
        "queue": "IT Support",
        "priority": "high",
        "language": "en",
    },
    {
        "ticket_id": "MOCK-0009",
        "subject": "Datenbankserver ausgefallen",
        "body": "Seit heute Morgen ist unser Produktionsdatenbankserver nicht "
        "erreichbar. Alle Anwendungen sind betroffen.",
        "answer": "Ein voller Speicher hat den Datenbankdienst gestoppt. Wir haben "
        "Speicher freigegeben und den Dienst neu gestartet. Bitte prüfen Sie, ob "
        "Ihre Anwendungen wieder verbunden sind.",
        "type": "Incident",
        "queue": "Technical Support",
        "priority": "high",
        "language": "de",
    },
    {
        "ticket_id": "MOCK-0010",
        "subject": "Printer on floor 3 not printing",
        "body": "The shared printer on floor 3 shows as offline for everyone.",
        "answer": "The printer lost its network lease. We assigned it a fixed "
        "address and it is back online. Please resend your print jobs.",
        "type": "Incident",
        "queue": "IT Support",
        "priority": "low",
        "language": "en",
    },
    {
        "ticket_id": "MOCK-0011",
        "subject": "Schedule CRM upgrade to version 5",
        "body": "Please plan the upgrade of our CRM instance to version 5 during "
        "the next maintenance window.",
        "answer": "We scheduled the CRM upgrade for the next maintenance window and "
        "will send you the change plan for approval beforehand.",
        "type": "Change",
        "queue": "Product Support",
        "priority": "medium",
        "language": "en",
    },
    {
        "ticket_id": "MOCK-0012",
        "subject": "Return a damaged monitor",
        "body": "The monitor we received has a cracked screen. How do we return it?",
        "answer": "Sorry about the damage. We created a return label for you; please "
        "pack the monitor in its original box. A replacement ships once the return "
        "is scanned.",
        "type": "Request",
        "queue": "Returns and Exchanges",
        "priority": "medium",
        "language": "en",
    },
    {
        "ticket_id": "MOCK-0013",
        "subject": "Software-Update für das Buchhaltungsprogramm",
        "body": "Wann wird das nächste Update für unser Buchhaltungsprogramm "
        "eingespielt?",
        "answer": "Das Update ist für das nächste Wartungsfenster geplant. Wir senden "
        "Ihnen vorab den Änderungsplan zur Freigabe.",
        "type": "Change",
        "queue": "Product Support",
        "priority": "low",
        "language": "de",
    },
    {
        "ticket_id": "MOCK-0014",
        "subject": "App crashes when exporting reports",
        "body": "The desktop app crashes every time I export a PDF report.",
        "answer": "This crash is a known issue in version 4.2. Please update to "
        "version 4.3, which fixes PDF export. Clearing the report cache also works "
        "as a temporary workaround.",
        "type": "Problem",
        "queue": "Technical Support",
        "priority": "medium",
        "language": "en",
    },
    {
        "ticket_id": "MOCK-0015",
        "subject": "Question about the parental leave policy",
        "body": "How many weeks of parental leave are employees entitled to?",
        "answer": "Please see the leave section of the HR handbook. Your HR business "
        "partner can confirm the details for your contract.",
        "type": "Request",
        "queue": "Human Resources",
        "priority": "low",
        "language": "en",
    },
    {
        "ticket_id": "MOCK-0016",
        "subject": "VPN-Verbindung bricht ständig ab",
        "body": "Die VPN-Verbindung im Homeoffice bricht alle paar Minuten ab.",
        "answer": "Bitte aktualisieren Sie den VPN-Client auf die neueste Version und "
        "wechseln Sie im Client auf das Protokoll IKEv2. Falls das Problem bleibt, "
        "senden Sie uns das Client-Protokoll.",
        "type": "Incident",
        "queue": "IT Support",
        "priority": "medium",
        "language": "de",
    },
]
