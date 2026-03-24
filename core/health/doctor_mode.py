# health/doctor_mode.py
class DoctorMode:
    def analyze(self, vitals):
        alerts = []

        hr = vitals.get("heart_rate")
        spo2 = vitals.get("spo2")

        if hr and (hr > 120 or hr < 45):
            alerts.append("Abnormal heart rate")

        if spo2 and spo2 < 92:
            alerts.append("Low oxygen level")

        if not alerts:
            return {"status": "stable"}

        return {
            "status": "alert",
            "issues": alerts
        }
