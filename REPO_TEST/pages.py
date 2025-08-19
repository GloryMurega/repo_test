#pages.py
from ._builtin import Page

from .models import C, Player
from otree.api import Currency as c

import json

from .scorer import responsibility_score, is_coherent
class ProlificID(Page):
    form_model = 'player'
    form_fields = ['prolific_id']

    def is_displayed(self):
        return self.round_number == 1

class DataPrivacy(Page):
    form_model = 'player'
    form_fields = ['data_privacy_consent']
    def is_displayed(self):
        return self.round_number == 1
    def error_message(self, values):
        if not values.get('data_privacy_consent'):
            return "You must tick the box to consent before continuing."

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

class Task_Results_Income(Page):
    def is_displayed(self):
        # Show after each income round
        return self.round_number in C.INCOME_ROUNDS

    def vars_for_template(self):
        round_num = self.round_number
        round1_player = self.participant.get_players()[0]

        # Original and revised choices
        original_choice = getattr(round1_player, f"income_choice_{round_num}", None)
        revised_choice = getattr(round1_player, f"income_choice_rev_{round_num}", None) or original_choice

        # Compute accuracy bonus
        correct_income = getattr(C, "CORRECT_INCOME_ANSWERS")[round_num - C.INCOME_ROUNDS[0]]
        accuracy_bonus = 0.50 if original_choice == correct_income else 0

        # Responsibility bonus
        responsibility_bonus = 0
        if round1_player.high_responsibility:
            responsibility_score = getattr(round1_player, f"responsibility_score_{round_num}", 0)
            responsibility_bonus = responsibility_score * 0.50

        # Total bonus
        total_bonus = accuracy_bonus + responsibility_bonus

        return {
            "round_num": round_num,
            "original_choice": original_choice,
            "revised_choice": revised_choice,
            "accuracy_bonus": accuracy_bonus,
            "responsibility_bonus": responsibility_bonus if responsibility_bonus else None,
            "total_bonus": total_bonus,
        }

class AttentionCheck(RequiresComprehensionPass):
    form_model = 'player'
    form_fields = ['response']

    def is_displayed(self):
        return self.round_number == C.INCOME_ROUNDS[-1] and super().is_displayed()

    def error_message(self, values):
        self.player.response_attempts += 1
        if values['response'].strip().lower() != 'sunshine':
            return "Please follow the instruction and type the correct word."

    def before_next_page(self):
        pass

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
            "eXplanation": f"REPO_TEST/{C.SONGS_EXPLANATIONS[idx].lower()}",
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

class Task_Results_Music(Page):
    def is_displayed(self):
        # Display only for music rounds after revision
        return self.round_number in C.SONGS_ROUNDS

    def vars_for_template(self):
        round_num = self.round_number
        round1_player = self.participant.get_players()[0]

        # Original and revised choices
        original_choice = getattr(round1_player, f"music_choice_{round_num}")
        revised_choice = getattr(round1_player, f"music_choice_rev_{round_num}")

        # Compute accuracy bonus based on tolerance
        correct_score = getattr(C, "CORRECT_MUSIC_SCORES")[round_num - C.SONGS_ROUNDS[0]]
        tolerance = 11
        accuracy_bonus = 0.50 if abs(float(original_choice) - float(correct_score)) <= tolerance else 0

        # Responsibility bonus if applicable
        responsibility_bonus = 0
        if round1_player.high_responsibility:
            responsibility_score = getattr(round1_player, f"responsibility_score_{round_num}", 0)
            responsibility_bonus = responsibility_score * 0.50

        # Total bonus
        total_bonus = accuracy_bonus + responsibility_bonus

        return {
            "round_num": round_num,
            "original_choice": original_choice,
            "revised_choice": revised_choice,
            "accuracy_bonus": accuracy_bonus,
            "responsibility_bonus": responsibility_bonus if responsibility_bonus else None,
            "total_bonus": total_bonus,
        }


class AITrustSurveyPost(RequiresComprehensionPass):
    form_model = 'player'
    form_fields = ['ai_trust_1', 'ai_trust_2', 'ai_trust_3']

    def is_displayed(self):
        return self.round_number == C.NUM_ROUNDS and not self.player.trust_early and super().is_displayed()


class Demographics(RequiresComprehensionPass):
    form_model = 'player'
    form_fields = ['age', 'gender','education_level', 'ai_experience']

    def is_displayed(self):
        return self.round_number == 1 and super().is_displayed()

    def before_next_page(self):
        self.participant.vars['age'] = self.player.age
        self.participant.vars['gender'] = self.player.gender
        self.participant.vars['ai_experience'] = self.player.ai_experience


class Debrief(RequiresComprehensionPass):
    def is_displayed(self):
        return self.round_number == C.NUM_ROUNDS and super().is_displayed()

    def before_next_page(self):
        participation_fee = self.session.config.get('participation_fee', c(2))
        round1_player = self.participant.get_players()[0]

        # Calculate bonuses for totals
        round1_player.calculate_bonuses()

        # Final payment = participation fee + total bonuses
        round1_player.final_payment = round1_player.total_bonus_payment + participation_fee

        # Store for oTree payment screen
        self.participant.payoff = round1_player.final_payment
        self.participant.vars['final_payment'] = float(round1_player.final_payment)

    def vars_for_template(self):
        round1_player = self.participant.get_players()[0]
        round1_player.calculate_bonuses()

        participation_fee = self.session.config['participation_fee']
        final_payment = round1_player.total_bonus_payment + participation_fee

        return {
            'participation_fee': participation_fee,
            'bonus_accuracy': round1_player.total_bonus_accuracy.to_real_world_currency(self.session),
            'bonus_responsibility': round1_player.total_bonus_responsibility.to_real_world_currency(self.session),
            'bonus_payment': round1_player.total_bonus_payment.to_real_world_currency(self.session),
            'final_payment': (round1_player.total_bonus_payment + participation_fee).to_real_world_currency(self.session),
            #'final_payment': final_payment.to_real_world_currency(self.session),
            'high_responsibility': round1_player.high_responsibility,
            'player': round1_player
        }


page_sequence = [
    ProlificID,
    DataPrivacy,
    ConsentAndComprehension,
    ComprehensionFail,
    NoConsent,
    Demographics,
    AITrustSurvey,
    ResponsibilityIntroIncome,
    ControlIntroIncome,
    Task_Info_Income,
    Task_Revise_Income,
    Task_Results_Income,
    AttentionCheck,
    ResponsibilityIntroSongs,
    ControlIntroSongs,
    Task_Info_Songs,
    Task_Revise_Songs,
    Task_Results_Music,
    AITrustSurveyPost,
    Debrief,
]


