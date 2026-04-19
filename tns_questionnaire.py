"""
TNS Multidimensional Analysis System
Tier C: Behavioral-Anchor Questionnaire Parser & Scorer

Clients complete this questionnaire before their scan session. Responses are
parsed, normalized, and scored on a 0-100 scale that matches the biomarker
scoring used by Tiers A and B, so all three tiers can be combined in a single
polygon visualization.

Six health categories are covered:
  body_composition   — movement habits, weight trend, training frequency
  heart_vascular     — family history, smoking, alcohol, fitness proxy, symptoms
  metabolic_function — energy consistency, afternoon crashes, cold sensitivity
  hormonal_balance   — libido, mood, thermoregulation, morning drive, cycle
  stress_recovery    — sleep quantity/quality, stress load, recovery, overwhelm
  lifestyle_fitness  — training type/intensity, steps, nutrition, hydration, protein

Hard rules enforced throughout this module:
  - The words "diagnose," "treat," "cure," "disease," "patient," "prescribe"
    are never used in any user-facing string.
  - All layperson strings are ≤ 25 words at an 8th-grade reading level.
  - Every item has both layperson_en and layperson_es strings.
  - Missing questionnaire items never cause a crash — they are skipped and
    weight is redistributed among present items.
  - All scores are integers in the range 0–100.

Usage
-----
    from tns_questionnaire import (
        parse_questionnaire,
        score_questionnaire_item,
        score_category_questionnaire,
        check_par_q,
        CATEGORY_ITEMS,
        ITEM_DEFS,
    )

    raw = {
        "q_sleep_hours_per_night": "7-7.9",
        "q_stress_interference_past_4_weeks": "few_times",
        "q_training_type": "mixed",
        # ... other responses
    }
    q = parse_questionnaire(raw)
    result = score_category_questionnaire("stress_recovery", q, sex="female")
    print(result["tier_c_score"])   # e.g. 76.4
    print(result["par_q_escalation"])  # False

    if check_par_q(q):
        print("PAR-Q escalation required before exercise programming.")
"""

from __future__ import annotations

from typing import Optional

# ── Category → item mapping ───────────────────────────────────────────────────
# q_training_frequency_days_per_week and q_alcohol_drinks_per_week intentionally
# appear in two categories each; deduplication is the polygon scorer's concern.

CATEGORY_ITEMS: dict[str, list[str]] = {
    "body_composition": [
        "q_activity_hours_per_week",
        "q_weight_trend_perception",
        "q_training_frequency_days_per_week",
    ],
    "heart_vascular": [
        "q_family_history_heart",
        "q_smoking",
        "q_alcohol_drinks_per_week",
        "q_cv_fitness_stairs_3_flights",
        "q_chest_pain_on_exertion",
    ],
    "metabolic_function": [
        "q_energy_consistency_days_per_week",
        "q_afternoon_crashes",
        "q_cold_sensitivity",
    ],
    "hormonal_balance": [
        "q_libido_past_4_weeks",
        "q_mood_swings_past_4_weeks",
        "q_thermoregulation",
        "q_morning_motivation",
        "q_menstrual_regularity",
    ],
    "stress_recovery": [
        "q_sleep_hours_per_night",
        "q_sleep_quality_rested_days",
        "q_stress_interference_past_4_weeks",
        "q_recovery_time_after_workout",
        "q_overwhelmed",
    ],
    "lifestyle_fitness": [
        "q_training_frequency_days_per_week",
        "q_training_type",
        "q_training_intensity_1to10",
        "q_daily_steps",
        "q_nutrition_whole_food_meals",
        "q_hydration_liters_per_day",
        "q_protein_meals_with_palm_serving",
    ],
}

# ── Item definitions ──────────────────────────────────────────────────────────
# Each entry describes one questionnaire item with its scoring map and
# bilingual layperson feedback strings (one per zone).
# Zones: "optimal" | "acceptable" | "suboptimal" | "concerning"
#
# "type" is one of:
#   "categorical" — value must match a key in "options"
#   "integer"     — value is an int (or int-castable string); scoring is
#                   computed by the score_questionnaire_item function using
#                   the "integer_bands" list of (min_inclusive, max_inclusive, score, zone)

ITEM_DEFS: dict[str, dict] = {

    # ── Body Composition ──────────────────────────────────────────────────────

    "q_activity_hours_per_week": {
        "label_en": "Weekly active hours",
        "label_es": "Horas activas por semana",
        "type": "categorical",
        "options": {
            "0 hours":   {"score": 10, "zone": "concerning"},
            "1-2 hours": {"score": 40, "zone": "suboptimal"},
            "3-4 hours": {"score": 70, "zone": "acceptable"},
            "5-7 hours": {"score": 85, "zone": "optimal"},
            "8+ hours":  {"score": 95, "zone": "optimal"},
        },
        "layperson_en": {
            "optimal":    "Great activity level — consistent movement supports healthy body composition.",
            "acceptable": "Solid activity habit. Adding one more session weekly can improve your results.",
            "suboptimal": "A little more movement each week would make a real difference for your body.",
            "concerning": "Starting with even 20-minute walks daily will jumpstart your progress significantly.",
        },
        "layperson_es": {
            "optimal":    "Excelente nivel de actividad — el movimiento constante apoya una composición corporal saludable.",
            "acceptable": "Buen hábito de actividad. Agregar una sesión más por semana puede mejorar tus resultados.",
            "suboptimal": "Un poco más de movimiento semanal marcaría una diferencia real en tu cuerpo.",
            "concerning": "Comenzar con caminatas de 20 minutos diarios acelerará tu progreso significativamente.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_weight_trend_perception": {
        "label_en": "Weight trend (self-reported)",
        "label_es": "Tendencia de peso (autopercibida)",
        "type": "categorical",
        "options": {
            "losing_happy":      {"score": 90, "zone": "optimal"},
            "stable":            {"score": 80, "zone": "optimal"},
            "gaining_unwanted":  {"score": 25, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "You're moving in the right direction — keep the habits that are working for you.",
            "acceptable": "Stable weight is a good foundation. We can fine-tune body composition from here.",
            "suboptimal": "Small consistent adjustments to nutrition and movement can reverse this trend.",
            "concerning": "Unintended weight gain is worth addressing with a structured plan.",
        },
        "layperson_es": {
            "optimal":    "Vas en la dirección correcta — mantén los hábitos que te están funcionando.",
            "acceptable": "El peso estable es una buena base. Desde aquí podemos afinar la composición corporal.",
            "suboptimal": "Ajustes pequeños y consistentes en nutrición y movimiento pueden revertir esta tendencia.",
            "concerning": "El aumento de peso no deseado vale la pena abordarlo con un plan estructurado.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_training_frequency_days_per_week": {
        "label_en": "Training days per week",
        "label_es": "Días de entrenamiento por semana",
        "type": "categorical",
        "options": {
            "0":  {"score": 10, "zone": "concerning"},
            "1":  {"score": 30, "zone": "suboptimal"},
            "2":  {"score": 50, "zone": "suboptimal"},
            "3":  {"score": 70, "zone": "acceptable"},
            "4":  {"score": 85, "zone": "optimal"},
            "5+": {"score": 95, "zone": "optimal"},
        },
        "layperson_en": {
            "optimal":    "Training this frequently builds real long-term fitness and body composition benefits.",
            "acceptable": "A solid training routine. One more session weekly can unlock your next level.",
            "suboptimal": "Building up to 3-4 days per week is the sweet spot for lasting change.",
            "concerning": "Starting with 2 days per week is totally achievable and will shift your results.",
        },
        "layperson_es": {
            "optimal":    "Entrenar con esta frecuencia construye beneficios reales a largo plazo en composición corporal.",
            "acceptable": "Rutina sólida de entrenamiento. Una sesión más por semana puede llevarte al siguiente nivel.",
            "suboptimal": "Llegar a 3-4 días por semana es el punto ideal para un cambio duradero.",
            "concerning": "Comenzar con 2 días por semana es completamente alcanzable y cambiará tus resultados.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    # ── Heart & Vascular ──────────────────────────────────────────────────────

    "q_family_history_heart": {
        "label_en": "Family history of heart problems",
        "label_es": "Historial familiar de problemas cardíacos",
        "type": "categorical",
        "options": {
            "no":      {"score": 95, "zone": "optimal"},
            "unknown": {"score": 60, "zone": "acceptable"},
            "yes":     {"score": 40, "zone": "suboptimal"},
        },
        "layperson_en": {
            "optimal":    "No known family history — a positive starting point for your cardiovascular health.",
            "acceptable": "Knowing your family history helps us personalize your heart health focus.",
            "suboptimal": "Family history is one factor — your lifestyle choices are the bigger lever here.",
            "concerning": "Family history raises awareness, but strong habits can significantly lower your personal risk.",
        },
        "layperson_es": {
            "optimal":    "Sin historial familiar conocido — un punto de partida positivo para tu salud cardiovascular.",
            "acceptable": "Conocer tu historial familiar nos ayuda a personalizar tu enfoque de salud cardíaca.",
            "suboptimal": "El historial familiar es un factor — tus hábitos de vida son la palanca más importante.",
            "concerning": "El historial familiar aumenta la conciencia, pero los buenos hábitos reducen significativamente tu riesgo personal.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_smoking": {
        "label_en": "Smoking status",
        "label_es": "Estado de tabaquismo",
        "type": "categorical",
        "options": {
            "never":         {"score": 95, "zone": "optimal"},
            "former_5plus":  {"score": 75, "zone": "optimal"},
            "former_recent": {"score": 50, "zone": "acceptable"},
            "current":       {"score": 15, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "No smoking history — your lungs and cardiovascular system thank you.",
            "acceptable": "Quitting is the best cardiovascular decision you made. Benefits continue for years.",
            "suboptimal": "Recent quitters see rapid cardiovascular improvements. You're on the right track.",
            "concerning": "Stopping smoking is the single highest-impact step for your heart and lung health.",
        },
        "layperson_es": {
            "optimal":    "Sin historial de tabaquismo — tus pulmones y sistema cardiovascular te lo agradecen.",
            "acceptable": "Dejar de fumar fue la mejor decisión cardiovascular. Los beneficios continúan por años.",
            "suboptimal": "Quienes dejaron recientemente ven mejoras cardiovasculares rápidas. Vas por buen camino.",
            "concerning": "Dejar de fumar es el paso de mayor impacto para tu salud cardíaca y pulmonar.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_alcohol_drinks_per_week": {
        "label_en": "Alcoholic drinks per week",
        "label_es": "Bebidas alcohólicas por semana",
        "type": "categorical",
        "options": {
            "0-3":  {"score": 90, "zone": "optimal"},
            "4-7":  {"score": 70, "zone": "acceptable"},
            "8-14": {"score": 40, "zone": "suboptimal"},
            "15+":  {"score": 15, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Low alcohol intake supports heart health, better sleep, and body composition.",
            "acceptable": "Moderate intake. Reducing by even 2 drinks per week can improve your metrics.",
            "suboptimal": "Higher alcohol intake affects recovery, body fat, and cardiovascular health noticeably.",
            "concerning": "Reducing alcohol intake is one of the fastest ways to improve multiple health markers.",
        },
        "layperson_es": {
            "optimal":    "Ingesta baja de alcohol — apoya la salud cardíaca, el sueño y la composición corporal.",
            "acceptable": "Ingesta moderada. Reducir incluso 2 bebidas por semana puede mejorar tus métricas.",
            "suboptimal": "Una ingesta mayor de alcohol afecta notablemente la recuperación, la grasa corporal y la salud cardiovascular.",
            "concerning": "Reducir el alcohol es una de las formas más rápidas de mejorar múltiples indicadores de salud.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_cv_fitness_stairs_3_flights": {
        "label_en": "Can climb 3 flights of stairs without stopping",
        "label_es": "Puede subir 3 tramos de escaleras sin detenerse",
        "type": "categorical",
        "options": {
            "yes":             {"score": 90, "zone": "optimal"},
            "with_difficulty": {"score": 50, "zone": "acceptable"},
            "no":              {"score": 20, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Good aerobic capacity — your heart and lungs handle moderate demands with ease.",
            "acceptable": "Some cardiovascular effort on stairs. Consistent cardio will make this easier soon.",
            "suboptimal": "Building aerobic base gradually will make daily activities feel much lighter.",
            "concerning": "Starting with short walks and building up gradually is the right first step for you.",
        },
        "layperson_es": {
            "optimal":    "Buena capacidad aeróbica — tu corazón y pulmones manejan demandas moderadas con facilidad.",
            "acceptable": "Algo de esfuerzo cardiovascular en escaleras. El cardio consistente lo hará más fácil pronto.",
            "suboptimal": "Construir tu base aeróbica gradualmente hará que las actividades diarias se sientan mucho más ligeras.",
            "concerning": "Comenzar con caminatas cortas y aumentar gradualmente es el primer paso correcto para ti.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_chest_pain_on_exertion": {
        "label_en": "Chest pain or pressure during physical activity",
        "label_es": "Dolor o presión en el pecho durante actividad física",
        "type": "categorical",
        "options": {
            "no":  {"score": 95, "zone": "optimal"},
            "yes": {"score":  0, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "No chest symptoms during activity — a good sign for your cardiovascular health.",
            "acceptable": "Occasional mild symptoms. Sharing this with a healthcare provider is a smart step.",
            "suboptimal": "Chest discomfort during exercise should be evaluated by a healthcare professional soon.",
            "concerning": "Chest pain during activity needs a medical evaluation before continuing an exercise program.",
        },
        "layperson_es": {
            "optimal":    "Sin síntomas en el pecho durante la actividad — una buena señal para tu salud cardiovascular.",
            "acceptable": "Síntomas leves ocasionales. Compartirlos con un profesional de salud es un paso inteligente.",
            "suboptimal": "El malestar en el pecho durante el ejercicio debe ser evaluado por un profesional de salud pronto.",
            "concerning": "El dolor en el pecho durante la actividad requiere evaluación médica antes de continuar un programa de ejercicio.",
        },
        "par_q_trigger": True,   # "yes" triggers PAR-Q escalation flag
        "skip_condition": None,
    },

    # ── Metabolic Function ────────────────────────────────────────────────────

    "q_energy_consistency_days_per_week": {
        "label_en": "Days per week with consistent energy",
        "label_es": "Días por semana con energía constante",
        "type": "categorical",
        "options": {
            "0-1": {"score": 10, "zone": "concerning"},
            "2-3": {"score": 35, "zone": "suboptimal"},
            "4-5": {"score": 65, "zone": "acceptable"},
            "6-7": {"score": 90, "zone": "optimal"},
        },
        "layperson_en": {
            "optimal":    "Consistent daily energy is a strong signal of good metabolic function.",
            "acceptable": "Mostly good energy. Small tweaks to sleep or nutrition can make it more reliable.",
            "suboptimal": "Frequent low-energy days often respond well to better sleep and balanced meals.",
            "concerning": "Very low energy most days is worth exploring — sleep, nutrition, and stress are key levers.",
        },
        "layperson_es": {
            "optimal":    "La energía diaria constante es una señal fuerte de buena función metabólica.",
            "acceptable": "Energía mayormente buena. Pequeños ajustes en sueño o nutrición pueden hacerla más confiable.",
            "suboptimal": "Los días de baja energía frecuentes responden bien a mejor sueño y comidas balanceadas.",
            "concerning": "Poca energía la mayoría de los días vale la pena explorar — el sueño, la nutrición y el estrés son factores clave.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_afternoon_crashes": {
        "label_en": "Afternoon energy crashes",
        "label_es": "Bajones de energía por la tarde",
        "type": "categorical",
        "options": {
            "never":     {"score": 95, "zone": "optimal"},
            "sometimes": {"score": 65, "zone": "acceptable"},
            "often":     {"score": 35, "zone": "suboptimal"},
            "daily":     {"score": 15, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "No afternoon slumps — your metabolism is handling the day's demands well.",
            "acceptable": "Occasional afternoon dips. Protein at lunch and limiting refined carbs usually help.",
            "suboptimal": "Frequent afternoon crashes often improve with balanced meals and better sleep.",
            "concerning": "Daily energy crashes may signal blood sugar swings. Nutrition timing can help a lot.",
        },
        "layperson_es": {
            "optimal":    "Sin bajones de tarde — tu metabolismo maneja bien las demandas del día.",
            "acceptable": "Bajones ocasionales por la tarde. Proteína en el almuerzo y menos carbohidratos refinados suelen ayudar.",
            "suboptimal": "Los bajones frecuentes por la tarde mejoran con comidas balanceadas y mejor sueño.",
            "concerning": "Los bajones diarios de energía pueden reflejar variaciones de azúcar en sangre. El timing nutricional puede ayudar mucho.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_cold_sensitivity": {
        "label_en": "Unusual sensitivity to cold",
        "label_es": "Sensibilidad inusual al frío",
        "type": "categorical",
        "options": {
            "no":          {"score": 90, "zone": "optimal"},
            "sometimes":   {"score": 60, "zone": "acceptable"},
            "yes":         {"score": 30, "zone": "suboptimal"},
        },
        "layperson_en": {
            "optimal":    "No unusual cold sensitivity — a good indicator of normal metabolic regulation.",
            "acceptable": "Occasional cold sensitivity can be normal. Hydration and iron intake are worth checking.",
            "suboptimal": "Persistent cold sensitivity is sometimes linked to low iron or sluggish metabolism.",
            "concerning": "Feeling cold most of the time, especially hands and feet, is worth discussing with your coach.",
        },
        "layperson_es": {
            "optimal":    "Sin sensibilidad inusual al frío — un buen indicador de regulación metabólica normal.",
            "acceptable": "La sensibilidad ocasional al frío puede ser normal. Vale revisar hidratación e ingesta de hierro.",
            "suboptimal": "La sensibilidad persistente al frío a veces se relaciona con bajo hierro o metabolismo lento.",
            "concerning": "Sentir frío la mayor parte del tiempo, especialmente en manos y pies, vale la pena comentarlo con tu coach.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    # ── Hormonal Balance ──────────────────────────────────────────────────────

    "q_libido_past_4_weeks": {
        "label_en": "Libido / sex drive (past 4 weeks)",
        "label_es": "Libido / deseo sexual (últimas 4 semanas)",
        "type": "categorical",
        "options": {
            "strong":        {"score": 90, "zone": "optimal"},
            "moderate_lower": {"score": 65, "zone": "acceptable"},
            "low_reduced":   {"score": 35, "zone": "suboptimal"},
            "very_low":      {"score": 15, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Strong drive is a good sign of balanced hormones and overall vitality.",
            "acceptable": "Moderate drive is common. Stress, sleep, and exercise all influence this significantly.",
            "suboptimal": "Reduced drive often responds well to better sleep, less stress, and regular training.",
            "concerning": "Very low drive can reflect hormone imbalances — sleep and stress are the first areas to address.",
        },
        "layperson_es": {
            "optimal":    "Un buen deseo es señal de hormonas equilibradas y vitalidad general.",
            "acceptable": "El deseo moderado es común. El estrés, el sueño y el ejercicio influyen mucho en esto.",
            "suboptimal": "El deseo reducido suele mejorar con mejor sueño, menos estrés y entrenamiento regular.",
            "concerning": "El deseo muy bajo puede reflejar desequilibrios hormonales — el sueño y el estrés son las primeras áreas a atender.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_mood_swings_past_4_weeks": {
        "label_en": "Mood swings (past 4 weeks)",
        "label_es": "Cambios de humor (últimas 4 semanas)",
        "type": "categorical",
        "options": {
            "rarely":           {"score": 90, "zone": "optimal"},
            "few_times":        {"score": 65, "zone": "acceptable"},
            "several_per_week": {"score": 35, "zone": "suboptimal"},
            "most_days":        {"score": 15, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Stable mood is a good indicator of hormonal and stress system balance.",
            "acceptable": "Occasional mood shifts are normal. Prioritizing sleep and recovery helps stabilize them.",
            "suboptimal": "Frequent mood changes can signal stress overload or disrupted sleep. Both are addressable.",
            "concerning": "Daily mood swings often improve with structured sleep, exercise, and stress management.",
        },
        "layperson_es": {
            "optimal":    "El humor estable es un buen indicador de equilibrio hormonal y del sistema de estrés.",
            "acceptable": "Los cambios ocasionales de humor son normales. Priorizar sueño y recuperación ayuda a estabilizarlos.",
            "suboptimal": "Los cambios frecuentes de humor pueden señalar sobrecarga de estrés o sueño alterado. Ambos son manejables.",
            "concerning": "Los cambios diarios de humor suelen mejorar con sueño estructurado, ejercicio y manejo del estrés.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_thermoregulation": {
        "label_en": "Unexplained hot flashes or night sweats",
        "label_es": "Sofocos o sudores nocturnos sin causa clara",
        "type": "categorical",
        "options": {
            "no":           {"score": 90, "zone": "optimal"},
            "occasionally": {"score": 60, "zone": "acceptable"},
            "frequently":   {"score": 25, "zone": "suboptimal"},
        },
        "layperson_en": {
            "optimal":    "No thermoregulation issues — body temperature control is working normally.",
            "acceptable": "Occasional hot flashes can be normal. Tracking when they occur may reveal patterns.",
            "suboptimal": "Frequent temperature swings are common during hormonal shifts and are worth tracking.",
            "concerning": "Regular hot flashes or night sweats can disrupt sleep and recovery — worth logging and discussing.",
        },
        "layperson_es": {
            "optimal":    "Sin problemas de termorregulación — el control de temperatura corporal funciona normalmente.",
            "acceptable": "Los sofocos ocasionales pueden ser normales. Registrar cuándo ocurren puede revelar patrones.",
            "suboptimal": "Los cambios frecuentes de temperatura son comunes durante cambios hormonales y vale la pena rastrearlos.",
            "concerning": "Los sofocos o sudores nocturnos regulares pueden interrumpir el sueño y la recuperación — vale registrarlos y comentarlos.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_morning_motivation": {
        "label_en": "Time to feel alert and motivated in the morning",
        "label_es": "Tiempo para sentirse alerta y motivado por la mañana",
        "type": "categorical",
        "options": {
            "within_15min": {"score": 90, "zone": "optimal"},
            "30_to_60min":  {"score": 65, "zone": "acceptable"},
            "over_hour":    {"score": 35, "zone": "suboptimal"},
            "rarely":       {"score": 15, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Quick morning alertness reflects healthy cortisol rhythm and good sleep quality.",
            "acceptable": "Moderate morning warm-up time. Consistent wake times and morning light can sharpen this.",
            "suboptimal": "Slow mornings often reflect disrupted sleep cycles or low cortisol — fixable with routine.",
            "concerning": "Rarely feeling motivated in the morning is a signal worth addressing with sleep and stress strategies.",
        },
        "layperson_es": {
            "optimal":    "La alerta matutina rápida refleja un ritmo sano de cortisol y buena calidad de sueño.",
            "acceptable": "Tiempo moderado de activación matutina. Horarios consistentes de despertar y luz matinal pueden agilizarlo.",
            "suboptimal": "Las mañanas lentas suelen reflejar ciclos de sueño alterados o bajo cortisol — corregible con rutina.",
            "concerning": "Rara vez sentirse motivado por la mañana es una señal que vale abordar con estrategias de sueño y estrés.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_menstrual_regularity": {
        "label_en": "Menstrual cycle regularity (women only)",
        "label_es": "Regularidad del ciclo menstrual (solo mujeres)",
        "type": "categorical",
        "options": {
            "regular":           {"score": 90, "zone": "optimal"},
            "irregular":         {"score": 45, "zone": "suboptimal"},
            "NA_contraception":  {"score": 70, "zone": "acceptable"},
            "NA_menopausal":     {"score": 70, "zone": "acceptable"},
        },
        "layperson_en": {
            "optimal":    "Regular cycles are a positive sign of hormonal rhythm and overall metabolic health.",
            "acceptable": "Hormonal contraception or menopause changes the cycle picture — noted for context.",
            "suboptimal": "Irregular cycles can have many causes including stress, nutrition, and exercise load.",
            "concerning": "Significant cycle irregularity is worth discussing with a healthcare professional.",
        },
        "layperson_es": {
            "optimal":    "Los ciclos regulares son una señal positiva de ritmo hormonal y salud metabólica general.",
            "acceptable": "Los anticonceptivos hormonales o la menopausia cambian el panorama del ciclo — anotado para contexto.",
            "suboptimal": "Los ciclos irregulares pueden tener muchas causas incluyendo estrés, nutrición y carga de ejercicio.",
            "concerning": "Una irregularidad significativa del ciclo vale la pena comentarla con un profesional de salud.",
        },
        "par_q_trigger": False,
        "skip_condition": "male",  # skip entirely when sex == "male"
    },

    # ── Stress & Recovery ─────────────────────────────────────────────────────

    "q_sleep_hours_per_night": {
        "label_en": "Sleep hours per night",
        "label_es": "Horas de sueño por noche",
        "type": "categorical",
        "options": {
            "8+":    {"score": 95, "zone": "optimal"},
            "7-7.9": {"score": 85, "zone": "optimal"},
            "6-6.9": {"score": 60, "zone": "acceptable"},
            "5-5.9": {"score": 35, "zone": "suboptimal"},
            "<5":    {"score": 10, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Excellent sleep habits — this supports recovery, hormones, and mental performance.",
            "acceptable": "Good sleep most nights. Consistent bedtimes can make this even better.",
            "suboptimal": "You're getting less sleep than your body needs for full recovery. Even 30 extra minutes matters.",
            "concerning": "Chronic short sleep raises stress hormones and slows recovery. This is a priority to address.",
        },
        "layperson_es": {
            "optimal":    "Excelente hábito de sueño: apoya la recuperación, las hormonas y el rendimiento mental.",
            "acceptable": "Buen sueño la mayoría de las noches. Horarios consistentes pueden mejorarlo.",
            "suboptimal": "Duermes menos de lo que tu cuerpo necesita para recuperarse. Incluso 30 minutos más importan.",
            "concerning": "Dormir poco crónicamente eleva el cortisol y frena la recuperación. Esto es una prioridad.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_sleep_quality_rested_days": {
        "label_en": "Days per week waking up feeling rested",
        "label_es": "Días por semana sintiéndose descansado al despertar",
        "type": "categorical",
        "options": {
            "almost_always": {"score": 95, "zone": "optimal"},
            "often":         {"score": 75, "zone": "optimal"},
            "sometimes":     {"score": 50, "zone": "acceptable"},
            "rarely":        {"score": 20, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Waking up refreshed most days means your body is truly recovering overnight.",
            "acceptable": "You often feel rested. Reducing screen time before bed can push this higher.",
            "suboptimal": "Only sometimes feeling rested suggests sleep quality needs attention, not just quantity.",
            "concerning": "Rarely waking up refreshed points to poor sleep quality — routine and environment matter here.",
        },
        "layperson_es": {
            "optimal":    "Despertar descansado la mayoría de los días significa que tu cuerpo se recupera verdaderamente durante la noche.",
            "acceptable": "A menudo te sientes descansado. Reducir pantallas antes de dormir puede mejorar esto.",
            "suboptimal": "Sentirse descansado solo a veces sugiere que la calidad del sueño necesita atención, no solo la cantidad.",
            "concerning": "Rara vez despertar descansado apunta a baja calidad de sueño — la rutina y el entorno importan aquí.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_stress_interference_past_4_weeks": {
        "label_en": "Stress interfering with daily life (past 4 weeks)",
        "label_es": "Estrés interfiriendo con la vida diaria (últimas 4 semanas)",
        "type": "categorical",
        "options": {
            "rarely":           {"score": 90, "zone": "optimal"},
            "few_times":        {"score": 65, "zone": "acceptable"},
            "several_per_week": {"score": 35, "zone": "suboptimal"},
            "most_days":        {"score": 15, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Low stress interference means your recovery and performance can stay high.",
            "acceptable": "Occasional stress is normal. Having a go-to reset routine helps keep it manageable.",
            "suboptimal": "Frequent stress impacts recovery, sleep, and body composition — worth building a buffer.",
            "concerning": "Daily stress interference is a top priority. Small daily decompression habits add up fast.",
        },
        "layperson_es": {
            "optimal":    "Poca interferencia del estrés significa que tu recuperación y rendimiento pueden mantenerse altos.",
            "acceptable": "El estrés ocasional es normal. Tener una rutina de reajuste ayuda a mantenerlo manejable.",
            "suboptimal": "El estrés frecuente impacta la recuperación, el sueño y la composición corporal — vale construir un amortiguador.",
            "concerning": "La interferencia diaria del estrés es una prioridad máxima. Los pequeños hábitos de descompresión suman rápido.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_recovery_time_after_workout": {
        "label_en": "Recovery time after a hard workout",
        "label_es": "Tiempo de recuperación después de un entrenamiento intenso",
        "type": "categorical",
        "options": {
            "same_day":         {"score": 90, "zone": "optimal"},
            "1_2_days":         {"score": 80, "zone": "optimal"},
            "3_plus_days":      {"score": 45, "zone": "suboptimal"},
            "rarely_recovered": {"score": 15, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Bouncing back quickly shows your body is adapting well to training stress.",
            "acceptable": "1-2 days is healthy recovery. Sleep, protein, and hydration keep this on track.",
            "suboptimal": "Taking 3+ days to recover may mean training load, sleep, or nutrition needs adjusting.",
            "concerning": "Feeling perpetually unrecovered signals your body needs more support — sleep and nutrition first.",
        },
        "layperson_es": {
            "optimal":    "Recuperarse rápido muestra que tu cuerpo se está adaptando bien al estrés del entrenamiento.",
            "acceptable": "1-2 días es una recuperación saludable. El sueño, la proteína y la hidratación mantienen esto en curso.",
            "suboptimal": "Tardar 3+ días en recuperarse puede significar que la carga de entrenamiento, el sueño o la nutrición necesitan ajuste.",
            "concerning": "Sentirse perpetuamente sin recuperar señala que tu cuerpo necesita más apoyo — sueño y nutrición primero.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_overwhelmed": {
        "label_en": "Feeling overwhelmed or unable to cope",
        "label_es": "Sentirse abrumado o incapaz de lidiar con las cosas",
        "type": "categorical",
        "options": {
            "never":     {"score": 90, "zone": "optimal"},
            "sometimes": {"score": 65, "zone": "acceptable"},
            "often":     {"score": 35, "zone": "suboptimal"},
            "always":    {"score": 10, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Feeling in control most of the time is a strong marker of resilience and wellbeing.",
            "acceptable": "Occasional overwhelm is human. Short daily recovery rituals build long-term resilience.",
            "suboptimal": "Frequent overwhelm drains recovery and focus. Adding structure to the day usually helps.",
            "concerning": "Feeling always overwhelmed affects every health dimension — this deserves focused attention now.",
        },
        "layperson_es": {
            "optimal":    "Sentirse en control la mayor parte del tiempo es un marcador fuerte de resiliencia y bienestar.",
            "acceptable": "El agobio ocasional es humano. Los rituales cortos de recuperación diaria construyen resiliencia a largo plazo.",
            "suboptimal": "El agobio frecuente drena la recuperación y el enfoque. Agregar estructura al día suele ayudar.",
            "concerning": "Sentirse siempre abrumado afecta todas las dimensiones de salud — esto merece atención enfocada ahora.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    # ── Lifestyle & Fitness ───────────────────────────────────────────────────

    "q_training_type": {
        "label_en": "Primary training type",
        "label_es": "Tipo principal de entrenamiento",
        "type": "categorical",
        "options": {
            "resistance": {"score": 85, "zone": "optimal"},
            "mixed":      {"score": 95, "zone": "optimal"},
            "cardio":     {"score": 75, "zone": "acceptable"},
            "none":       {"score": 10, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Combining resistance and cardio gives you the best of both fitness worlds.",
            "acceptable": "Resistance training builds the muscle that drives metabolism and body composition.",
            "suboptimal": "Cardio is a great base. Adding resistance work 2x/week amplifies your results.",
            "concerning": "Starting any consistent movement habit will shift your health metrics in the right direction.",
        },
        "layperson_es": {
            "optimal":    "Combinar resistencia y cardio te da lo mejor de ambos mundos del fitness.",
            "acceptable": "El entrenamiento de resistencia construye el músculo que impulsa el metabolismo y la composición corporal.",
            "suboptimal": "El cardio es una gran base. Agregar trabajo de resistencia 2x/semana amplifica tus resultados.",
            "concerning": "Comenzar cualquier hábito de movimiento consistente moverá tus métricas de salud en la dirección correcta.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_training_intensity_1to10": {
        "label_en": "Typical training intensity (1 = very easy, 10 = maximum effort)",
        "label_es": "Intensidad típica de entrenamiento (1 = muy fácil, 10 = esfuerzo máximo)",
        "type": "integer",
        # Integer bands: list of (min_inclusive, max_inclusive, score, zone)
        # Peak zone is 7-8; both too low and too high are suboptimal.
        "integer_bands": [
            (1,  2, 15, "concerning"),
            (3,  4, 40, "suboptimal"),
            (5,  6, 70, "acceptable"),
            (7,  8, 90, "optimal"),
            (9, 10, 70, "acceptable"),
        ],
        "layperson_en": {
            "optimal":    "Training at 7-8/10 intensity hits the sweet spot for adaptation without overtraining.",
            "acceptable": "Good effort level. Mixing intensities across the week optimizes recovery and results.",
            "suboptimal": "Either very easy or near-maximal most sessions limits long-term progress.",
            "concerning": "Very low intensity misses the training stimulus needed for real body composition change.",
        },
        "layperson_es": {
            "optimal":    "Entrenar a 7-8/10 de intensidad da en el punto óptimo para adaptación sin sobreentrenamiento.",
            "acceptable": "Buen nivel de esfuerzo. Mezclar intensidades durante la semana optimiza la recuperación y los resultados.",
            "suboptimal": "Sesiones casi siempre muy suaves o casi máximas limitan el progreso a largo plazo.",
            "concerning": "La intensidad muy baja no genera el estímulo de entrenamiento necesario para un cambio real de composición corporal.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_daily_steps": {
        "label_en": "Average daily steps",
        "label_es": "Pasos diarios promedio",
        "type": "categorical",
        "options": {
            "10000+":    {"score": 95, "zone": "optimal"},
            "7500-9999": {"score": 80, "zone": "optimal"},
            "5000-7499": {"score": 60, "zone": "acceptable"},
            "3000-4999": {"score": 35, "zone": "suboptimal"},
            "<3000":     {"score": 15, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "10,000+ daily steps is excellent for metabolic health and body composition.",
            "acceptable": "Strong step count. This level of daily movement supports your training results.",
            "suboptimal": "A moderate step count. Parking further away or walking calls are easy wins.",
            "concerning": "Low daily steps limit your non-exercise activity, which drives a big chunk of daily calorie use.",
        },
        "layperson_es": {
            "optimal":    "Más de 10,000 pasos diarios es excelente para la salud metabólica y la composición corporal.",
            "acceptable": "Buen conteo de pasos. Este nivel de movimiento diario apoya tus resultados de entrenamiento.",
            "suboptimal": "Un conteo moderado de pasos. Estacionar más lejos o caminar durante llamadas son ganancias fáciles.",
            "concerning": "Los pasos diarios bajos limitan tu actividad fuera del ejercicio, que impulsa gran parte del uso calórico diario.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_nutrition_whole_food_meals": {
        "label_en": "Proportion of meals based on whole foods",
        "label_es": "Proporción de comidas basadas en alimentos enteros",
        "type": "categorical",
        "options": {
            "all":       {"score": 95, "zone": "optimal"},
            "most_75":   {"score": 80, "zone": "optimal"},
            "half":      {"score": 55, "zone": "acceptable"},
            "less_half": {"score": 30, "zone": "suboptimal"},
            "few_none":  {"score": 10, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Whole food-based meals provide the micronutrients and fiber your body needs to perform.",
            "acceptable": "Mostly whole foods is a solid foundation. Swapping one processed meal daily helps.",
            "suboptimal": "Half of your meals are whole food-based. Gradual shifts here have a big compound effect.",
            "concerning": "Very few whole food meals means your body is likely missing key nutrients for recovery.",
        },
        "layperson_es": {
            "optimal":    "Las comidas basadas en alimentos enteros aportan los micronutrientes y fibra que tu cuerpo necesita para rendir.",
            "acceptable": "Mayoría de alimentos enteros es una base sólida. Cambiar una comida procesada al día ayuda.",
            "suboptimal": "La mitad de tus comidas son de alimentos enteros. Los cambios graduales aquí tienen un gran efecto acumulado.",
            "concerning": "Muy pocas comidas de alimentos enteros significa que tu cuerpo probablemente carece de nutrientes clave para la recuperación.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_hydration_liters_per_day": {
        "label_en": "Daily water intake (liters)",
        "label_es": "Ingesta diaria de agua (litros)",
        "type": "categorical",
        "options": {
            "3+":  {"score": 95, "zone": "optimal"},
            "2-3": {"score": 80, "zone": "optimal"},
            "1-2": {"score": 45, "zone": "suboptimal"},
            "<1":  {"score": 15, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Great hydration supports every system — joints, digestion, focus, and metabolism.",
            "acceptable": "Good hydration level. Aim for the lower end of 3L+ on training days.",
            "suboptimal": "Low water intake limits nutrient transport, recovery, and energy. A water bottle helps.",
            "concerning": "Very low hydration affects nearly every body function. Starting with 1.5L daily is the goal.",
        },
        "layperson_es": {
            "optimal":    "Excelente hidratación apoya cada sistema — articulaciones, digestión, enfoque y metabolismo.",
            "acceptable": "Buen nivel de hidratación. Apunta al límite inferior de 3L+ en días de entrenamiento.",
            "suboptimal": "La ingesta baja de agua limita el transporte de nutrientes, la recuperación y la energía. Una botella de agua ayuda.",
            "concerning": "La hidratación muy baja afecta casi todas las funciones del cuerpo. Comenzar con 1.5L diarios es el objetivo.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },

    "q_protein_meals_with_palm_serving": {
        "label_en": "Meals per day with a palm-sized protein serving",
        "label_es": "Comidas al día con una porción de proteína del tamaño de la palma",
        "type": "categorical",
        "options": {
            "all_3":    {"score": 95, "zone": "optimal"},
            "two_of_3": {"score": 75, "zone": "acceptable"},
            "one_of_3": {"score": 45, "zone": "suboptimal"},
            "rarely":   {"score": 15, "zone": "concerning"},
        },
        "layperson_en": {
            "optimal":    "Protein at every meal supports muscle retention, satiety, and metabolic rate.",
            "acceptable": "2 of 3 meals with protein is solid. The missing meal is your easiest improvement.",
            "suboptimal": "Most of your meals are low in protein, which limits muscle maintenance and recovery.",
            "concerning": "Rarely hitting protein targets makes it hard to preserve muscle and feel satisfied after meals.",
        },
        "layperson_es": {
            "optimal":    "Proteína en cada comida apoya la retención muscular, la saciedad y el metabolismo.",
            "acceptable": "2 de 3 comidas con proteína es sólido. La comida faltante es tu mejora más fácil.",
            "suboptimal": "La mayoría de tus comidas son bajas en proteína, lo que limita el mantenimiento muscular y la recuperación.",
            "concerning": "Rara vez alcanzar los objetivos de proteína dificulta preservar músculo y sentirse satisfecho después de comer.",
        },
        "par_q_trigger": False,
        "skip_condition": None,
    },
}

# ── PAR-Q trigger items ───────────────────────────────────────────────────────
# Items whose specific response values require escalation before exercise.
_PAR_Q_TRIGGERS: dict[str, set] = {
    "q_chest_pain_on_exertion": {"yes"},
}

# ── Valid categories ──────────────────────────────────────────────────────────
_VALID_CATEGORIES: frozenset[str] = frozenset(CATEGORY_ITEMS.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_value(item_name: str, raw_value) -> Optional[str]:
    """
    Coerce *raw_value* to the canonical string key used in ITEM_DEFS.

    For categorical items, str(raw_value).strip() is tried against the
    options dict (case-sensitive first, then case-insensitive fallback).

    For integer items, int(raw_value) is returned as an int.
    Returns None if coercion fails or the item is not in ITEM_DEFS.
    """
    if item_name not in ITEM_DEFS:
        return None
    if raw_value is None:
        return None

    defn = ITEM_DEFS[item_name]

    if defn["type"] == "integer":
        try:
            return int(raw_value)
        except (ValueError, TypeError):
            return None

    # Categorical: normalize to string
    candidate = str(raw_value).strip()
    options = defn.get("options", {})

    # Exact match first
    if candidate in options:
        return candidate

    # Case-insensitive fallback
    candidate_lower = candidate.lower()
    for key in options:
        if key.lower() == candidate_lower:
            return key

    # For training_frequency, allow bare integers like 0, 1, 2, 3, 4
    if item_name == "q_training_frequency_days_per_week":
        try:
            int_val = int(candidate)
            str_val = str(int_val)
            if str_val in options:
                return str_val
            if int_val >= 5:
                return "5+"
        except (ValueError, TypeError):
            pass

    return None


def _score_integer_item(defn: dict, value: int) -> tuple[int, str]:
    """
    Evaluate *value* against the integer_bands list.
    Returns (score, zone). Falls back to (0, "concerning") if no band matches.
    """
    for (lo, hi, score, zone) in defn["integer_bands"]:
        if lo <= value <= hi:
            return score, zone
    return 0, "concerning"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def parse_questionnaire(raw: dict) -> dict:
    """
    Normalize raw questionnaire input.

    Accepts a flat dict of {item_name: raw_value} pairs. Unknown keys are
    silently dropped. Values are coerced to the canonical type expected by
    each item definition (string key for categorical, int for integer).

    String / int variants are both handled — e.g. "3" and 3 are equivalent
    for q_training_frequency_days_per_week.

    Returns
    -------
    dict
        {item_name: normalized_value} for recognized items whose values
        could be coerced. Items that fail coercion are omitted (treated as
        missing downstream).
    """
    result: dict = {}
    for item_name, raw_value in raw.items():
        if item_name not in ITEM_DEFS:
            continue
        normalized = _normalize_value(item_name, raw_value)
        if normalized is not None:
            result[item_name] = normalized
    return result


def score_questionnaire_item(
    item_name: str,
    value,
    sex: str = "male",
) -> Optional[dict]:
    """
    Score a single questionnaire item.

    Parameters
    ----------
    item_name : str
        Must be a key in ITEM_DEFS.
    value :
        The normalized value for the item (as returned by parse_questionnaire).
        Raw values are also accepted and will be normalized internally.
    sex : str
        "male" or "female". Used to skip sex-specific items (e.g.
        q_menstrual_regularity is skipped for males).

    Returns
    -------
    dict or None
        None is returned when:
          - item_name is not in ITEM_DEFS
          - value is None after normalization
          - the item has a skip_condition that matches *sex*

        Otherwise returns:
        {
            "name": str,
            "value": (normalized value),
            "score": int,         # 0-100
            "zone": str,          # optimal / acceptable / suboptimal / concerning
            "layperson_en": str,
            "layperson_es": str,
        }
    """
    if item_name not in ITEM_DEFS:
        return None

    defn = ITEM_DEFS[item_name]

    # Skip-condition check (sex-based)
    skip_cond = defn.get("skip_condition")
    if skip_cond is not None and sex.lower() == skip_cond.lower():
        return None

    # Normalize value
    normalized = _normalize_value(item_name, value)
    if normalized is None:
        return None

    # Compute score and zone
    if defn["type"] == "integer":
        score, zone = _score_integer_item(defn, normalized)
    else:
        option_entry = defn["options"].get(normalized)
        if option_entry is None:
            return None
        score = option_entry["score"]
        zone = option_entry["zone"]

    layperson_en = defn["layperson_en"].get(zone, "")
    layperson_es = defn["layperson_es"].get(zone, "")

    return {
        "name": item_name,
        "value": normalized,
        "score": score,
        "zone": zone,
        "layperson_en": layperson_en,
        "layperson_es": layperson_es,
    }


def score_category_questionnaire(
    category: str,
    questionnaire: dict,
    sex: str = "male",
) -> dict:
    """
    Score the Tier C (questionnaire) portion of one health category.

    Missing items are skipped and their weight is redistributed evenly
    across the items that were scored, so partial questionnaires always
    produce a valid score — they never crash and never return None.

    Parameters
    ----------
    category : str
        One of the keys in CATEGORY_ITEMS.
    questionnaire : dict
        Normalized questionnaire dict (from parse_questionnaire or raw).
    sex : str
        "male" or "female".

    Returns
    -------
    dict
        {
            "category": str,
            "tier": "c",
            "items_scored": list[dict],   # score_questionnaire_item results
            "items_missing": list[str],   # item names not provided / not scoreable
            "tier_c_score": float,        # equal-weight average of scored items (0-100)
            "par_q_escalation": bool,     # True if any PAR-Q trigger fired
            "confidence": str,            # "full" | "partial"
        }
    """
    if category not in _VALID_CATEGORIES:
        raise ValueError(
            f"Unknown category '{category}'. Valid categories: {sorted(_VALID_CATEGORIES)}"
        )

    item_names = CATEGORY_ITEMS[category]
    items_scored: list[dict] = []
    items_missing: list[str] = []
    par_q_flag = False

    for item_name in item_names:
        raw_value = questionnaire.get(item_name)

        # Attempt to score
        result = score_questionnaire_item(item_name, raw_value, sex=sex)

        if result is None:
            # Either missing, unanswerable, or sex-skipped
            # Sex-skipped items (q_menstrual_regularity for males) are
            # NOT counted as missing — they're expected to be absent.
            defn = ITEM_DEFS.get(item_name)
            if defn is not None:
                skip_cond = defn.get("skip_condition")
                if skip_cond is not None and sex.lower() == skip_cond.lower():
                    # Intentionally skipped — not missing
                    continue
            items_missing.append(item_name)
        else:
            items_scored.append(result)
            # Check PAR-Q trigger
            if ITEM_DEFS[item_name].get("par_q_trigger", False):
                trigger_values = _PAR_Q_TRIGGERS.get(item_name, set())
                if str(result["value"]).lower() in {v.lower() for v in trigger_values}:
                    par_q_flag = True

    # Compute tier C score — equal weight across scored items
    if items_scored:
        tier_c_score = sum(r["score"] for r in items_scored) / len(items_scored)
    else:
        tier_c_score = 0.0

    # Determine confidence
    # An item is "expected" if it's not sex-skipped
    expected_items = []
    for item_name in item_names:
        defn = ITEM_DEFS.get(item_name)
        if defn is None:
            continue
        skip_cond = defn.get("skip_condition")
        if skip_cond is not None and sex.lower() == skip_cond.lower():
            continue
        expected_items.append(item_name)

    confidence = "full" if len(items_missing) == 0 else "partial"

    return {
        "category": category,
        "tier": "c",
        "items_scored": items_scored,
        "items_missing": items_missing,
        "tier_c_score": round(tier_c_score, 2),
        "par_q_escalation": par_q_flag,
        "confidence": confidence,
    }


def check_par_q(questionnaire: dict) -> bool:
    """
    Check whether any PAR-Q trigger response is present.

    Currently the only PAR-Q trigger is:
      q_chest_pain_on_exertion == "yes"

    Returns True immediately when a trigger is found so that the calling
    code can halt exercise programming and escalate to a professional.

    Parameters
    ----------
    questionnaire : dict
        Raw or parsed questionnaire dict.

    Returns
    -------
    bool
        True if a PAR-Q escalation condition is detected, False otherwise.
    """
    for item_name, trigger_values in _PAR_Q_TRIGGERS.items():
        raw = questionnaire.get(item_name)
        if raw is None:
            continue
        normalized = _normalize_value(item_name, raw)
        if normalized is not None and str(normalized).lower() in {
            v.lower() for v in trigger_values
        }:
            return True
    return False
