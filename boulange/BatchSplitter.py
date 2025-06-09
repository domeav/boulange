#!/bin/env python3

from itertools import combinations

def split_quantities(quantites, recipients):
    sorted_quantites = sorted(quantites.items(), key=lambda x: x[1], reverse=True)
    sorted_recipients = sorted(recipients.items(), key=lambda x: x[1], reverse=True)

    repartition = {}

    def backtrack(quantite_index, recipients_utilises):
        if quantite_index == len(sorted_quantites):
            return True

        nom_quantite, quantite = sorted_quantites[quantite_index]

        # Essayer de trouver un seul récipient qui peut contenir la quantité
        for nom_recipient, capacite in sorted_recipients:
            if nom_recipient not in recipients_utilises and capacite >= quantite:
                recipients_utilises.add(nom_recipient)
                repartition[nom_quantite] = {nom_recipient: 100}

                if backtrack(quantite_index + 1, recipients_utilises):
                    return True

                recipients_utilises.remove(nom_recipient)
                del repartition[nom_quantite]

        # Si aucun récipient unique ne peut contenir la quantité, essayer des combinaisons
        for i in range(2, len(recipients) + 1):
            for combo in combinations(sorted_recipients, i):
                total = sum(capacite for nom_recipient, capacite in combo)
                if total >= quantite:
                    recipients_combines = []
                    temp_recipients_utilises = set(recipients_utilises)
                    distribution = {}

                    quantite_restante = quantite
                    for nom_r, cap_r in sorted(combo, key=lambda x: x[1]):
                        if nom_r not in temp_recipients_utilises:
                            if quantite_restante > 0:
                                # Calculer la quantité à mettre dans ce récipient pour un remplissage uniforme
                                fill_amount = min(cap_r, (quantite_restante / (i - len(recipients_combines))))
                                pourcentage = round((fill_amount / quantite) * 100, 2)
                                recipients_combines.append(nom_r)
                                temp_recipients_utilises.add(nom_r)
                                distribution[nom_r] = pourcentage
                                quantite_restante -= fill_amount

                    if quantite_restante <= 0:
                        recipients_utilises.update(temp_recipients_utilises)
                        repartition[nom_quantite] = distribution

                        if backtrack(quantite_index + 1, recipients_utilises):
                            return True

                        for nom_r in recipients_combines:
                            recipients_utilises.remove(nom_r)
                        del repartition[nom_quantite]

        return False

    if backtrack(0, set()):
        return repartition
    else:
        return None
