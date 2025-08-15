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
            #round1_player.save()
        # Set the final_payment (bonus + participation fee)
        round1_player.final_payment = (
                round1_player.bonus_payment + c(2)  # or use self.session.config['participation_fee']
        )
        #round1_player.save()
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



<h2>Thank You for Participating!</h2>

<p>You have completed all {{ C.NUM_ROUNDS }} tasks in this study.</p>

<hr>

<h3>Your Bonus Payment</h3>
<ul>
  <li><strong>Participation Fee:</strong> {{ participation_fee }}</li>
  <li><strong>Accuracy Bonus:</strong> {{ bonus_accuracy }}</li>
  {% if high_responsibility %}
     <li><strong>Responsibility Bonus:</strong> {{ bonus_responsibility }}</li>
  {% endif %}
  <li><strong>Total Bonus:</strong> <b>{{ bonus_payment }}</b></li>
  <li><strong>Final Payment:</strong> <b>{{ final_payment }}</b></li>
</ul>

<hr>
<p>
You may now close this window or return to the platform.
</p>

<p>To complete your participation, please click the link below:</p>
<p>
  <a href="https://app.prolific.com/submissions/complete?cc=XXXXXXX" target="_blank">
    <strong>Submit on Prolific</strong>
  </a>
</p>
{% endblock %}
