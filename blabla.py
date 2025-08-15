class Results(Page):
    def vars_for_template(self):
        round_num = self.round_number

        # Use field_maybe_none to be safe; fallback to zero or empty string
        bonus_accuracy = self.player.field_maybe_none(f"bonus_acc_{round_num}") or c(0)
        bonus_responsibility = self.player.field_maybe_none(f"bonus_resp_{round_num}") or c(0)
        responsibility_score = self.player.field_maybe_none(f"responsibility_score_{round_num}") or 0
        responsibility_feedback = self.player.field_maybe_none(f"responsibility_feedback_{round_num}") or ""

        return {
            "bonus_accuracy": bonus_accuracy,
            "bonus_responsibility": bonus_responsibility,
            "responsibility_score": responsibility_score,
            "responsibility_feedback": responsibility_feedback,
        }

class CombinedResults(Page):
    def is_displayed(self):
        return self.round_number == C.NUM_ROUNDS

    def vars_for_template(self):
        all_players = self.player.in_all_rounds()

        # Use 0 currency as default if field is None
        combined_accuracy_bonus = sum(
            p.field_maybe_none("bonus_accuracy") or c(0) for p in all_players
        )

        combined_responsibility_bonus = sum(
            p.field_maybe_none("bonus_responsibility") or c(0) for p in all_players
        )

        combined_total_bonus = sum(
            p.field_maybe_none("bonus_payment") or c(0) for p in all_players
        )

        participation_fee = c(2)  # or from Constants

        final_payment = combined_total_bonus + participation_fee

        return dict(
            combined_accuracy_bonus=combined_accuracy_bonus,
            combined_responsibility_bonus=combined_responsibility_bonus,
            combined_total_bonus=combined_total_bonus,
            participation_fee=participation_fee,
            final_payment=final_payment,
        )

    #pages.py
    from ._builtin import Page
    from .models import C, Player
    from otree.api import Currency as c

    import json

    try:
        from responsibility_ai.scorer import responsibility_score
    except ImportError:
        from .scorer import responsibility_score

    from .scorer import is_coherent

    class ConsentAndComprehension(Page):
        form_model = 'player'
        form_fields = [
            'consent',
            'comp_task_understanding',
            'comp_model_accuracy',
            'comp_payment'
        ]

        def is_displayed(self):
            return self.round_number == 1 and not self.player.comprehension_failed

        def error_message(self, values):
            if values['consent'] is False:
                return "You must consent to participate in the study to continue."

            incorrect = []
            if values['comp_task_understanding'] != '6':
                incorrect.append('task understanding')
            if values['comp_model_accuracy'] != '86% & 72%':
                incorrect.append('model accuracy')
            if values['comp_payment'] != '£2.00 + bonus':
                incorrect.append('payment')

            if incorrect:
                self.player.comprehension_attempts += 1
                if self.player.comprehension_attempts >= 2:
                    self.player.comprehension_failed = True
                return "Some answers are incorrect. Please try again." if self.player.comprehension_attempts < 2 else None

        def before_next_page(self):
            self.player.comprehension_failed = not (
                    self.player.comp_task_understanding == '6' and
                    self.player.comp_model_accuracy == '86% & 72%' and
                    self.player.comp_payment == '£2.00 + bonus'
            )

    class ComprehensionFail(Page):
        def is_displayed(self):
            return self.round_number == 1 and self.player.comprehension_failed

    class NoConsent(Page):
        def is_displayed(self):
            return self.round_number == 1 and self.player.consent is False

    class RequiresComprehensionPass(Page):
        def is_displayed(self):
            return not self.player.comprehension_failed

    class ResponsibilityIntroIncome(RequiresComprehensionPass):
        def is_displayed(self):
            return self.round_number == 1 and self.player.high_responsibility

    class ControlIntroIncome(RequiresComprehensionPass):
        def is_displayed(self):
            return self.round_number == 1 and not self.player.high_responsibility

    class ResponsibilityIntroSongs(RequiresComprehensionPass):
        def is_displayed(self):
            return self.round_number == 4 and self.player.high_responsibility

    class ControlIntroSongs(RequiresComprehensionPass):
        def is_displayed(self):
            return self.round_number == 4 and not self.player.high_responsibility

    class AITrustSurvey(RequiresComprehensionPass):
        form_model = 'player'
        form_fields = ['ai_trust_1', 'ai_trust_2', 'ai_trust_3']

        def is_displayed(self):
            return self.round_number == 1 and self.player.trust_early and super().is_displayed()

    class Task_Info_Income(RequiresComprehensionPass):
        form_model = 'player'

        def is_displayed(self):
            return self.round_number in C.INCOME_ROUNDS and super().is_displayed()

        def get_form_fields(self):
            return [f'income_choice_{self.round_number}']

        def vars_for_template(self):
            return {
                'person_desc': self.player.person_desc(),
                'question': "Into which income group would you classify this person?",
                'description': self.player.person_desc()
            }

        def before_next_page(self):
            value = getattr(self.player, f'income_choice_{self.round_number}', None)
        # print(f"[DEBUG] Round {self.round_number}: income_choice_{self.round_number} = {value}")

    class Task_Revise_Income(RequiresComprehensionPass):
        form_model = 'player'

        def is_displayed(self):
            return self.round_number in C.INCOME_ROUNDS and super().is_displayed()

        def get_form_fields(self):
            fields = [f'income_choice_rev_{self.round_number}']
            if self.player.high_responsibility:
                fields.append(f'justification_{self.round_number}')
            return fields

        def vars_for_template(self):
            idx = self.round_number - C.INCOME_ROUNDS[0]
            return {
                "AI_Prediction": C.INCOME_PREDICTIONS[idx],
                "eXplanation": f"REPO_TEST/{C.INCOME_EXPLANATIONS[idx]}",
                "income_description": self.player.person_desc(),
                "high_responsibility": self.player.high_responsibility,
                "income_choice_rev_field": f"income_choice_rev_{self.round_number}",
                "justification_field": f'justification_{self.round_number}' if self.player.high_responsibility else None
            }

        def error_message(self, values):
            rev = values.get(f'income_choice_rev_{self.round_number}')
            if not rev:
                return "Please make a selection before continuing."
            if self.player.high_responsibility:
                just = values.get(f'justification_{self.round_number}', '').strip()
                if not just:
                    return "Please provide a justification before continuing."
                if not is_coherent(just, threshold=0.9):
                    return "Your justification doesn't seem meaningful. Please revise and provide a clearer answer."

        def before_next_page(self):
            round1_player = self.participant.get_players()[0]
            round_num = self.round_number
            orig = getattr(self.player, f"income_choice_{round_num}", None)
            rev = getattr(self.player, f"income_choice_rev_{round_num}", None) or orig
            justification = self.player.field_maybe_none(f"justification_{self.round_number}") or ""

            setattr(round1_player, f"income_choice_{round_num}", orig)
            setattr(round1_player, f"income_choice_rev_{round_num}", rev)
            setattr(round1_player, f"justification_{round_num}", justification or "")

            if rev != orig:
                setattr(round1_player, f"income_changed_{round_num}", True)

            if round1_player.high_responsibility and justification and justification.strip():
                round1_player.apply_responsibility_score(round_num)
            round1_player.calculate_round_bonus(round_num)

            # Optional debug
            # print(f"--- DEBUG ROUND {round_num} ---")
            # print(f"Original Income Choice: {orig}")
            # print(f"Revised Income Choice: {rev}")
            # print(f"Justification: '{justification}'")
            # print(f"Responsibility score: {getattr(round1_player, f'responsibility_score_{round_num}', 'N/A')}")
            # print(f"Bonus Accuracy: {getattr(round1_player, f'bonus_acc_{round_num}', 'N/A')}")
            # print(f"Bonus Responsibility: {getattr(round1_player, f'bonus_resp_{round_num}', 'N/A')}")
            # print(f"High responsibility: {round1_player.high_responsibility}")

    class AttentionCheck(RequiresComprehensionPass):
        form_model = 'player'
        form_fields = ['attention_response']

        def is_displayed(self):
            return self.round_number == C.INCOME_ROUNDS[-1] and super().is_displayed()

        def error_message(self, values):
            self.player.response_attempts += 1
            self.player.attention_response = values['attention_response']
            # No save call needed
            if values['attention_response'].strip().lower() != 'sunshine':
                return "Please follow the instruction and type the correct word."

    class Task_Info_Songs(RequiresComprehensionPass):
        form_model = 'player'

        def is_displayed(self):
            return self.round_number in C.SONGS_ROUNDS and super().is_displayed()

        def get_form_fields(self):
            return [f'music_choice_{self.round_number}']

        def vars_for_template(self):
            return {
                'song_desc': self.player.song_desc(),
                'question': "What score would you give this song?",
                'description': self.player.song_desc()
            }

        def before_next_page(self):
            value = getattr(self.player, f'music_choice_{self.round_number}', None)
            # print(f"[DEBUG] Round {self.round_number}: music_choice_{self.round_number} = {value}")

    class Task_Revise_Songs(RequiresComprehensionPass):
        form_model = 'player'

        def is_displayed(self):
            return self.round_number in C.SONGS_ROUNDS and super().is_displayed()

        def get_form_fields(self):
            fields = [f'music_choice_rev_{self.round_number}']
            if self.player.high_responsibility:
                fields.append(f'justification_{self.round_number}')
            return fields

        def vars_for_template(self):
            idx = self.round_number - C.SONGS_ROUNDS[0]
            return {
                "AI_Prediction": C.SONGS_PREDICTIONS[idx],
                "eXplanation": f"REPO_TEST/{C.SONGS_EXPLANATIONS[idx]}",
                "song_description": self.player.song_desc(),
                "high_responsibility": self.player.high_responsibility,
                "music_choice_rev_field": f"music_choice_rev_{self.round_number}",
                "justification_field": f'justification_{self.round_number}' if self.player.high_responsibility else None
            }

        def error_message(self, values):
            rev = values.get(f'music_choice_rev_{self.round_number}')
            if rev is None:
                return "You must provide a revised prediction."
            try:
                val = float(rev)
            except (ValueError, TypeError):
                return "Please enter a number like 87.3 or 59.0."
            if not (1 <= val <= 100):
                return "The score must be between 1 and 100."
            if self.player.high_responsibility:
                just = values.get(f'justification_{self.round_number}', '').strip()
                if not just:
                    return "Please provide a justification before continuing."
                if not is_coherent(just, threshold=0.9):
                    return "Your justification doesn't seem meaningful. Please revise and provide a clearer answer."

        def before_next_page(self):  # if self.round_number in [4, 5, 6]:
            # self.calculate_round_bonus(self.round_number)
            round1_player = self.participant.get_players()[0]
            orig = getattr(self.player, f"music_choice_{self.round_number}")
            rev = getattr(self.player, f"music_choice_rev_{self.round_number}") or orig
            justification = self.player.field_maybe_none(f"justification_{self.round_number}") or ""

            setattr(round1_player, f"music_choice_{self.round_number}", orig)
            setattr(round1_player, f"music_choice_rev_{self.round_number}", rev)
            setattr(round1_player, f"justification_{self.round_number}", justification)

            if rev != orig:
                setattr(round1_player, f"music_changed_{self.round_number}", True)
            if round1_player.high_responsibility and justification.strip():
                round1_player.apply_responsibility_score(self.round_number)

            # Calculate and store bonuses on round1_player
            round1_player.calculate_round_bonus(self.round_number)

            # DEBUG print to see what's going on
            # print(f"--- DEBUG ROUND {self.round_number} ---")
            # print(f"Original: {orig}")
            # print(f"Revised: {rev}")
            # print(f"Justification: '{justification}'")
            # print(f"Responsibility score: {getattr(round1_player, f'responsibility_score_{self.round_number}', 'N/A')}")
            # print(f"Bonus Accuracy: {getattr(round1_player, f'bonus_acc_{self.round_number}', 'N/A')}")
            # print(f"Bonus Responsibility: {getattr(round1_player, f'bonus_resp_{self.round_number}', 'N/A')}")
            # print(f"High responsibility: {round1_player.high_responsibility}")

    class AITrustSurveyPost(RequiresComprehensionPass):
        form_model = 'player'
        form_fields = ['ai_trust_1', 'ai_trust_2', 'ai_trust_3']

        def is_displayed(self):
            return self.round_number == C.NUM_ROUNDS and not self.player.trust_early and super().is_displayed()

    class Demographics(RequiresComprehensionPass):
        form_model = 'player'
        form_fields = ['age', 'gender', 'ai_experience']

        def is_displayed(self):
            return self.round_number == 1 and super().is_displayed()

        def before_next_page(self):
            self.participant.vars['age'] = self.player.age
            self.participant.vars['gender'] = self.player.gender
            self.participant.vars['ai_experience'] = self.player.ai_experience

    class Debrief(RequiresComprehensionPass):
        def is_displayed(self):
            show = self.round_number == C.NUM_ROUNDS and super().is_displayed()
            print(f"[Debrief] is_displayed returns {show} at round {self.round_number}")
            return show

        def before_next_page(self):
            round1_player = self.participant.get_players()[0]
            # Assuming calculate_bonuses updates total bonus fields (optional if still needed)
            round1_player.calculate_bonuses()
            round1_player.save()

            # Use the total bonus properties here instead of individual bonus fields
            self.participant.vars['final_bonus_accuracy'] = float(
                round1_player.total_bonus_accuracy.to_real_world_currency())
            self.participant.vars['final_bonus_responsibility'] = float(
                round1_player.total_bonus_responsibility.to_real_world_currency())
            self.participant.vars['final_bonus_payment'] = float(
                round1_player.total_bonus_payment.to_real_world_currency())

            print(f"[Debrief] Calculated bonuses: "
                  f"Accuracy={round1_player.total_bonus_accuracy}, "
                  f"Responsibility={round1_player.total_bonus_responsibility}, "
                  f"Total={round1_player.total_bonus_payment}")

        def vars_for_template(self):
            round1_player = self.participant.get_players()[0]
            self.participant.vars['final_payment'] = float(
                round1_player.total_bonus_payment.to_real_world_currency(self.session)
            )
            print(
                f"[Debug Vars] bonus_accuracy={round1_player.bonus_accuracy}, "
                f"bonus_responsibility={round1_player.bonus_responsibility}, "
                f"bonus_payment={round1_player.bonus_payment}"
            )
            return {
                'high_responsibility': round1_player.high_responsibility,
                'participation_fee': 2.00,
                'bonus_accuracy': round1_player.total_bonus_accuracy,
                'bonus_responsibility': round1_player.total_bonus_responsibility,
                'bonus_payment': round1_player.total_bonus_payment,
                'player': round1_player,
                'C': C,
            }

    class CombinedResults(RequiresComprehensionPass):
        def is_displayed(self):
            return self.round_number == C.NUM_ROUNDS and super().is_displayed()

        def before_next_page(self):
            round1_player = self.participant.get_players()[0]
            if round1_player.bonus_payment == 0 or round1_player.bonus_payment is None:
                round1_player.calculate_bonuses()
                round1_player.save()
            # Set the final_payment (bonus + participation fee)
            round1_player.final_payment = (
                    round1_player.bonus_payment + c(2)  # or use self.session.config['participation_fee']
            )
            round1_player.save()
            self.participant.vars['final_payment'] = float(
                round1_player.final_payment.to_real_world_currency(self.session))

        def vars_for_template(self):
            round1_player = self.participant.get_players()[0]
            participation_fee = c(2)  # or self.session.config['participation_fee']

            return {
                'combined_accuracy_bonus': round1_player.bonus_accuracy.to_real_world_currency(self.session),
                'combined_responsibility_bonus': round1_player.bonus_responsibility.to_real_world_currency(
                    self.session),
                'combined_total_bonus': round1_player.bonus_payment.to_real_world_currency(self.session),
                'participation_fee': participation_fee.to_real_world_currency(self.session),
                'final_payment': round1_player.final_payment.to_real_world_currency(self.session)
            }

    page_sequence = [
        ConsentAndComprehension,
        ComprehensionFail,
        NoConsent,
        Demographics,
        AITrustSurvey,
        ResponsibilityIntroIncome,
        ControlIntroIncome,
        Task_Info_Income,
        Task_Revise_Income,
        AttentionCheck,
        ResponsibilityIntroSongs,
        ControlIntroSongs,
        Task_Info_Songs,
        Task_Revise_Songs,
        AITrustSurveyPost,
        # Results,
        CombinedResults,
        Debrief,

    ]
#models.py
from otree.api import *
import random
import json
from otree.api import Currency as c

import sys
#sys.setrecursionlimit(new_limit)

try:
    from responsibility_ai.scorer import responsibility_score
except ImportError:
    from .scorer import responsibility_score

class C(BaseConstants):
    NAME_IN_URL = 'REPO_TEST'
    PLAYERS_PER_GROUP = None
    NUM_ROUNDS = 6  # 3 income + 3 songs
    INCOME_ROUNDS = [1, 2, 3]
    SONGS_ROUNDS = [4, 5, 6]
    TREATMENTS = [(0, 0), (0, 1), (1, 0), (1, 1)]

    INCOME_PREDICTIONS = ["Middle income", "Middle income", "High income"]
    CORRECT_INCOME_ANSWERS = ["Middle income", "High income", "Low income"]
    INCOME_EXPLANATIONS = [
        "income_1_20335401.png",
        "income_2_8089602.png",
        "income_3_21250202.png",
    ]
    SONGS_PREDICTIONS = ["65.8", "25.2", "36.1"]
    CORRECT_MUSIC_SCORES = ["75.4", "69.4", "86.7"]
    SONGS_EXPLANATIONS = [
        "song_1_414.png",
        "song_2_3042.png",
        "Song_3_1656.png",
    ]
    PARTICIPATION_FEE = [c(2)]
    ACCURACY_BONUS_PER_ROUND = [c(0.50)]
    RESPONSIBILITY_BONUS_MULTIPLIER =[c(0.50)]

class Subsession(BaseSubsession):
    def creating_session(self):
        for p in self.get_players():
            if self.round_number == 1:
                resp_int, trust_int = random.choice(C.TREATMENTS)
                p.participant.vars['high_responsibility'] = bool(resp_int)
                p.participant.vars['trust_early'] = bool(trust_int)

            p.high_responsibility = p.participant.vars['high_responsibility']
            p.trust_early = p.participant.vars['trust_early']
            p.survey_first = p.trust_early

class Group(BaseGroup):
    pass

class Player(BasePlayer):
    # Conditions (set in creating_session)
    high_responsibility = models.BooleanField()
    trust_early = models.BooleanField()
    survey_first = models.BooleanField()

    # Consent & Comprehension
    consent = models.BooleanField(choices=[[True,'I consent'],[False,'I do not consent']],widget=widgets.RadioSelect)
    comp_task_understanding = models.StringField(
        label="How many total task rounds will you complete in this study?",
        choices=["2", "4", "6"]
    )
    comp_model_accuracy = models.StringField(
        label="What is the approximate accuracy of the AI models?",
        choices=["72% & 100%", "86% & 100%", "86% & 72%"]
    )
    comp_payment = models.StringField(
        label="What payment are you eligible for after completing the study?",
        choices=["£2.00 + bonus", "£3.00 + bonus", "£9 flat"]
    )
    #TrustSurvey
    ai_trust_1 = models.IntegerField(
        label="I trust the recommendations by AI-driven systems.",
        choices=[[i, str(i)] for i in range(1, 8)],
        widget=widgets.RadioSelectHorizontal,
    )
    ai_trust_2 = models.IntegerField(
        label="Recommended decisions through AI processes are trustworthy",
        choices=[[i, str(i)] for i in range(1, 8)],
        widget=widgets.RadioSelectHorizontal,
    )
    ai_trust_3 = models.IntegerField(
        label="I believe that the AI systems results are reliable.",
        choices=[[i, str(i)] for i in range(1, 8)],
        widget=widgets.RadioSelectHorizontal,
    )
    comprehension_failed = models.BooleanField(initial=False)
    comprehension_attempts = models.IntegerField(initial=0)

    # Demographics
    age = models.IntegerField(min=18, max=99)
    gender = models.StringField(choices=["Male","Female","Non-binary","Prefer not to answer"],widget=widgets.RadioSelectHorizontal)
    ai_experience = models.StringField(choices=["Very familiar","Somewhat familiar","A little","Not at all"],widget=widgets.RadioSelectHorizontal)

    # Attention check
    attention_response = models.StringField(blank=True)
    response_attempts = models.IntegerField(initial=0)

    # Income and song tasks & justifications
    income_choice_1 = models.StringField(choices=["High income","Middle income","Low income"],widget=widgets.RadioSelect)
    income_choice_rev_1 = models.StringField(choices=["High income","Middle income","Low income"],widget=widgets.RadioSelect)
    justification_1 = models.LongStringField(blank=True)

    income_choice_2 = models.StringField(choices=["High income","Middle income","Low income"],widget=widgets.RadioSelect)
    income_choice_rev_2 = models.StringField(choices=["High income","Middle income","Low income"],widget=widgets.RadioSelect)
    justification_2 = models.LongStringField(blank=True)

    income_choice_3 = models.StringField(choices=["High income","Middle income","Low income"],widget=widgets.RadioSelect)
    income_choice_rev_3 = models.StringField(choices=["High income","Middle income","Low income"],widget=widgets.RadioSelect)
    justification_3 = models.LongStringField(blank=True)

    music_choice_4 = models.FloatField(min=1, max=100)
    music_choice_rev_4 = models.FloatField(min=1, max=100)
    justification_4 = models.LongStringField(blank=True)

    music_choice_5 = models.FloatField(min=1, max=100)
    music_choice_rev_5 = models.FloatField(min=1, max=100)
    justification_5 = models.LongStringField(blank=True)

    music_choice_6 = models.FloatField(min=1, max=100)
    music_choice_rev_6 = models.FloatField(min=1, max=100)
    justification_6 = models.LongStringField(blank=True)

    # Change flags
    income_changed_1 = models.BooleanField(initial=False)
    income_changed_2 = models.BooleanField(initial=False)
    income_changed_3 = models.BooleanField(initial=False)

    music_changed_4 = models.BooleanField(initial=False)
    music_changed_5 = models.BooleanField(initial=False)
    music_changed_6 = models.BooleanField(initial=False)

    # Per-round responsibility scores, feedback, details
    responsibility_score_1 = models.FloatField(initial=0)
    responsibility_score_2 = models.FloatField(initial=0)
    responsibility_score_3 = models.FloatField(initial=0)
    responsibility_score_4 = models.FloatField(initial=0)
    responsibility_score_5 = models.FloatField(initial=0)
    responsibility_score_6 = models.FloatField(initial=0)

    responsibility_feedback_1 = models.LongStringField(blank=True)
    responsibility_feedback_2 = models.LongStringField(blank=True)
    responsibility_feedback_3 = models.LongStringField(blank=True)
    responsibility_feedback_4 = models.LongStringField(blank=True)
    responsibility_feedback_5 = models.LongStringField(blank=True)
    responsibility_feedback_6 = models.LongStringField(blank=True)

    responsibility_details_1 = models.LongStringField(blank=True)
    responsibility_details_2 = models.LongStringField(blank=True)
    responsibility_details_3 = models.LongStringField(blank=True)
    responsibility_details_4 = models.LongStringField(blank=True)
    responsibility_details_5 = models.LongStringField(blank=True)
    responsibility_details_6 = models.LongStringField(blank=True)

    bonus_acc_1 = models.CurrencyField(initial=0)
    bonus_resp_1 = models.CurrencyField(initial=0)
    bonus_acc_2 = models.CurrencyField(initial=0)
    bonus_resp_2 = models.CurrencyField(initial=0)
    bonus_acc_3= models.CurrencyField(initial=0)
    bonus_resp_3 = models.CurrencyField(initial=0)
    bonus_acc_4 = models.CurrencyField(initial=0)
    bonus_resp_4 = models.CurrencyField(initial=0)
    bonus_acc_5 = models.CurrencyField(initial=0)
    bonus_resp_5 = models.CurrencyField(initial=0)
    bonus_acc_6 = models.CurrencyField(initial=0)
    bonus_resp_6 = models.CurrencyField(initial=0)

    # Aggregate bonuses
    bonus_accuracy = models.CurrencyField(initial=0)
    bonus_responsibility = models.CurrencyField(initial=0)
    bonus_payment = models.CurrencyField(initial=0)
    final_payment = models.CurrencyField(initial=0)

    def person_desc(self):
        descriptions = {
            1: "Person A: A fully employed single woman with no migration background. She works a standard full-time schedule of 40 hours across 5 days per week. She has completed 14.5 years of education. Her health is reported as good, and her work satisfaction is very high (9 out of 10). "
               "She drinks alcohol, but her smoking and union membership status are unknown. She has no siblings and her parents both had vocational degrees. Financially, she has no wealth and is €3,000(~ $3,270 or £2,540 ) in debt. Her age and job classification are unspecified.",
            2: "Person B: A 64-year-old married man with no migration background. He is fully employed in a highly qualified position, working 40 hours over 5 days per week. He has completed 12 years of education, does not smoke, drinks alcohol, and reports low health - bad. "
               "His work satisfaction is moderate (rated 4 out of 10). He is not a union member, has one sibling, and comes from a family where his father had a vocational degree and his mother did not. "
               "Financially he has €35,000(~ $41,110 or £30,320) in gross wealth and no debt.",
            3: "Person C: This person is married, fully employed in a highly qualified position, and works an intensive schedule of 55 hours over just 2 days per week. They have no migration background and no siblings. They have completed 15 years of education. Their work satisfaction is very low (1 out of 10). "
               "Their financial status includes €116,000(~ $135,590 or £100,500) in gross wealth and €44,794(~ $52,370 or £38,810) in debt. Their age, gender, alcohol consumption, smoking status, and union membership are unknown. Their health is rated as satisfactory and both parents had vocational degrees."
        }
        return descriptions.get(self.round_number)

    def song_desc(self):
        descriptions = {
            4: """Song A: The track "Pretty - Sped Up" by MEYY was released on June 7, 2023.
                                    On Spotify, it has 1,867,282 streams, appears in 498 playlists, and reaches 521,031 listeners.
                                    On YouTube, it has 485,422 views and 12,137 likes.
                                    The song has 4,300,000 TikTok posts with 99,212,673 likes and 1,267,424,672 views.
                                    It appears in 1 Amazon playlist, has 3,897 Pandora streams across 21 track stations, and 15,462 Shazam counts.
                                    It is not marked as explicit.""",
            5: """Song B: The track "This Is The Thanks I Get?! - From 'Wish'" by Chris Pine was released on October 25, 2023.
                                    Spotify streams total 15,090,071, with the track appearing in 1,405 playlists and reaching 7,665,573 listeners.
                                    On YouTube, it has 6,176,518 views and 49,281 likes.
                                    TikTok has 2,600,000 posts, 15,257,747 likes, and 182,005,109 views.
                                    The song reaches 297,428 listeners through YouTube playlists.
                                    It appears in 16 Apple Music playlists, has 11 AirPlay spins, 1 Deezer playlist with 18 listeners, and 7 Amazon playlists.
                                    Pandora streams are 572,150 across 1,913 track stations.
                                    Shazam counts total 25,335.
                                    It is not explicit.""",
            6: """Song C: The track "Pink Skies" by Zach Bryan was released on May 24, 2024.
                                    It has 60,240,739 Spotify streams, appears in 4,611 playlists reaching 98,570,633 listeners.
                                    YouTube views are 3,322,959 with 65,840 likes.
                                    TikTok engagement includes 107,100 likes and 843,600 views.
                                    The track has a YouTube playlist reach of 235,974,273, appears in 82 Apple Music playlists, and has 734 AirPlay spins and 1 SiriusXM spin.
                                    Deezer playlists total 26 with a reach of 5,164,376, Amazon playlists total 79, Pandora streams total 5,006,041 across 2,349 track stations, and Soundcloud streams are 521,223.
                                    Shazam counts are 156,886.
                                    The track is not explicit."""
        }
        return descriptions.get(self.round_number)

    @property
    def average_responsibility_score(self):
        scores = [
            getattr(self, f'responsibility_score_{r}', None)
            for r in C.INCOME_ROUNDS + C.SONGS_ROUNDS
        ]
        valid_scores = [s for s in scores if s is not None]
        return round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else "N/A"

    @property
    def total_bonus_accuracy(self):
        bonus_values = [
            getattr(self, f'bonus_acc_{r}', c(0))
            for r in C.INCOME_ROUNDS + C.SONGS_ROUNDS
        ]
        return sum(bonus_values, c(0))

    @property
    def total_bonus_responsibility(self):
        bonus_values = [
            getattr(self, f'bonus_resp_{r}', c(0))
            for r in C.INCOME_ROUNDS + C.SONGS_ROUNDS
        ]
        return sum(bonus_values, c(0))

    @property
    def total_bonus_payment(self):
        participation_fee = c(2)
        return self.total_bonus_accuracy + self.total_bonus_responsibility + participation_fee

    def export_vars(self):
        parent = super().export_vars()
        return parent + [
            round(self.total_bonus_accuracy.to_real_world_currency(), 2),
            round(self.total_bonus_responsibility.to_real_world_currency(), 2),
            round(self.total_bonus_payment.to_real_world_currency(), 2),
        ]

    #def export_labels(self): - working @property and normal calc
        #parent = super().export_labels()
        #return parent + ['Bonus accuracy', 'Bonus responsibility', 'Total bonus']
    def export_vars(self):
        parent = super().export_vars()
        return parent + [
            round(self.bonus_accuracy.to_real_world_currency(), 2),
            round(self.bonus_responsibility.to_real_world_currency(), 2),
            round(self.bonus_payment.to_real_world_currency(), 2),
            round(self.final_payment.to_real_world_currency(), 2),
        ]

    def export_labels(self):
        parent = super().export_labels()
        return parent + ['Bonus accuracy', 'Bonus responsibility', 'Bonus payment', 'Final payment']
    # --- Helper methods ---
    def apply_responsibility_score(self, round_number):
        field = f"justification_{round_number}"
        justification = self.field_maybe_none(field)
        if self.high_responsibility and justification and justification.strip():
            final, pos, neg, expl, evid, *_ = responsibility_score(justification)
            setattr(self, f"responsibility_score_{round_number}", final)
            feedback = f"Positive phrases: {', '.join(pos)}" if pos else "No patterns found."
            setattr(self, f"responsibility_feedback_{round_number}", feedback)
            details = {
                "pos": list(pos),
                "neg": list(neg),
                "expl": list(expl),
                "evid": list(evid)
            }
            # Store JSON string of details - make sure you have responsibility_details_# fields as LongStringField
            setattr(self, f"responsibility_details_{round_number}", json.dumps(details))
            #self.save()

    def collect_task_data(self):
        data = []
        income_truth = dict(zip(C.INCOME_ROUNDS, C.CORRECT_INCOME_ANSWERS))
        music_truth = dict(zip(C.SONGS_ROUNDS, [float(x) for x in C.CORRECT_MUSIC_SCORES]))
        tolerance = 11

        for r in range(1, C.NUM_ROUNDS + 1):
            task = 'income' if r in C.INCOME_ROUNDS else 'music'

            orig = self.field_maybe_none(f"{task}_choice_{r}")
            rev = self.field_maybe_none(f"{task}_choice_rev_{r}")
            just = self.field_maybe_none(f"justification_{r}") or 0
            score = self.field_maybe_none(f"responsibility_score_{r}") or 0

            # Determine accuracy
            if task == 'income':
                correct = orig == income_truth.get(r)
            else:
                try:
                    correct = orig is not None and abs(float(orig) - music_truth.get(r, 0)) <= tolerance
                except (ValueError, TypeError):
                    correct = False

            # Calculate bonuses as oTree Currency objects
            bonus_acc = c(0.50) if correct else c(0)
            bonus_resp = c(score * 0.50) if (self.high_responsibility and just) else c(0)

            # Save bonuses to player fields
            setattr(self, f"bonus_acc_{r}", bonus_acc)
            setattr(self, f"bonus_resp_{r}", bonus_resp)

            data.append({
                'round': r,
                'task': task,
                'orig': orig,
                'rev': rev,
                'just': just,
                'acc': int(correct),
                'score': score,
                'bonus_acc': bonus_acc,
                'bonus_resp': bonus_resp,
            })

        return data

    def field_maybe_none(self, field_name):
        value = self.__dict__.get(field_name, None)
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == '':
            return None
        return value

    def calculate_round_bonus(self, round_number):
        task = 'income' if round_number in C.INCOME_ROUNDS else 'music'
        orig = getattr(self, f"{task}_choice_{round_number}", None)
        score = getattr(self, f"responsibility_score_{round_number}", c(0))
        justification = self.field_maybe_none(f"justification_{round_number}") or ""
       #justification = self.field_maybe_none(f"justification_{self.round_number}") or ""

        if task == 'income':
            correct = orig == C.CORRECT_INCOME_ANSWERS[round_number - C.INCOME_ROUNDS[0]]
        else:
            try:
                idx = C.SONGS_ROUNDS.index(round_number)
                correct_value = float(C.CORRECT_MUSIC_SCORES[idx])
                correct = orig is not None and abs(float(orig) - correct_value) <= 10
            except Exception:
                correct = False

        bonus_acc = c(0.5) if correct else c(0)
        bonus_resp = c(score * 0.5) if self.high_responsibility and justification.strip() else c(0)

        setattr(self, f"bonus_acc_{round_number}", bonus_acc)
        setattr(self, f"bonus_resp_{round_number}", bonus_resp)

    def calculate_bonuses(self):
        print("[DEBUG] Calculating bonuses...")
        acc_total = c(0)
        resp_total = c(0)
        for round_number in range(1, 7):
            acc = getattr(self, f'bonus_acc_{round_number}', c(0))
            resp = getattr(self, f'bonus_resp_{round_number}', c(0))
            print(f"Round {round_number}: acc={acc}, resp={resp}")
            acc_total += acc
            resp_total += resp
        print(f"Total accuracy bonus: {acc_total}, Total responsibility bonus: {resp_total}")
        self.bonus_accuracy = acc_total
        self.bonus_responsibility = resp_total
        self.bonus_payment = acc_total + resp_total