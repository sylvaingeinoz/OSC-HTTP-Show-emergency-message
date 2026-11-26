# Pilotage avec Bitfocus Companion

Companion envoie ses commandes **vers le Pi**. Il n’est pas nécessaire d’activer le contrôle distant de Companion lui-même. Les modules officiels sont [Generic — HTTP Requests](https://bitfocus.io/connections/generic-http) et [Generic — OSC](https://bitfocus.io/connections/generic-osc). Les intitulés exacts des champs peuvent varier selon la version du module.

Dans les exemples, remplacer `192.168.1.50` par l’IP du Pi. Aucun identifiant, clé ou en-tête Authorization n’est requis.

## HTTP : action de bouton

Ajouter une connexion **Generic: HTTP Requests**, puis une action de requête HTTP sur l’appui du bouton :

- Méthode : `POST`
- URL : `http://192.168.1.50:8080/api/command`
- En-tête `Content-Type` : `application/json`
- Corps : l’un des objets JSON ci-dessous, sans les balises de code.

Si le module sépare une URL de base et un chemin, utiliser respectivement `http://192.168.1.50:8080` et `/api/command`. Ne configurer qu’une seule action d’envoi sur l’appui ; pas de commande noire implicite au relâchement.

| Bouton | Corps JSON |
| --- | --- |
| Changement micro | `{"mode":"text","text":"LÉA · MICRO 2\nChangement côté cour"}` |
| Reprise | `{"mode":"text","text":"REPRISE"}` |
| Stop clignotant | `{"mode":"stop"}` |
| Stop personnalisé | `{"mode":"stop","text":"STOP SHOW\nRestez en place"}` |
| Noir immédiat | `{"mode":"black"}` |
| Heure | `{"mode":"clock"}` |
| Minuterie 5 min | `{"mode":"timer","seconds":300}` |
| Nouvel An suisse 2027 | `{"mode":"countdown","target":"2027-01-01T00:00:00+01:00"}` |
| Mire | `{"mode":"test"}` |
| Prolonger sans redémarrer le compteur | `{"mode":"keepalive"}` |

Une réponse HTTP 200 confirme l’acceptation par le service. 400 signifie une commande invalide, 413 un corps trop grand, 415 un mauvais type de contenu. Un retour 200 ne confirme pas le signal réel sur la TV.

Essai équivalent depuis un terminal :

```sh
curl --fail-with-body -X POST 'http://192.168.1.50:8080/api/command' \
  -H 'Content-Type: application/json' \
  --data '{"mode":"stop"}'
```

Le texte est du texte brut, jamais du HTML. Dans JSON, échapper les guillemets par `\"` et représenter les retours à la ligne par `\n`. Pour des variables Companion contenant du texte arbitraire, veiller à leur encodage JSON ; OSC avec un argument chaîne peut être plus simple.

## OSC : action de bouton

Ajouter une connexion **Generic: OSC**, transport **UDP**, hôte `192.168.1.50`, port `9000`. Ajouter une action d’envoi OSC avec chemin et arguments typés. **Les arguments contiennent uniquement les données de la commande.** En migrant depuis la version 1.1, retirer le premier argument de clé de chaque bouton OSC.

| Chemin OSC | Arguments dans l’ordre | Signature OSC |
| --- | --- | --- |
| `/show/text` | chaîne `LÉA · MICRO 2` | `,s` |
| `/show/stop` | aucun | `,` |
| `/show/stop` (personnalisé) | chaîne `STOP SHOW` | `,s` |
| `/show/black` | aucun | `,` |
| `/show/clock` | aucun | `,` |
| `/show/timer` | entier `300` ou flottant `300.0` | `,i` ou `,f` |
| `/show/countdown` | chaîne `2027-01-01T00:00:00+01:00` | `,s` |
| `/show/test` | aucun | `,` |
| `/show/keepalive` | aucun | `,` |

La signature est descriptive : Companion la construit à partir des types, ne pas l’ajouter au chemin. Pour « REPRISE », envoyer `/show/text` avec la chaîne `REPRISE`. Utiliser une action OSC capable de transmettre plusieurs arguments lorsque nécessaire.

Pris en charge : messages OSC 1.0 **simples**, chaînes UTF-8 (`s`), entiers 32 bits (`i`) et flottants 32 bits (`f`). Maximum 16 384 octets par datagramme, tout compris. Les bundles, timetags, types supplémentaires et paquets malformés sont rejetés. Pas de réponse OSC, de diffusion de feedback ou de planification OSC différée dans cette version. Ne pas activer l’agrégation en bundles dans l’émetteur.

Tester sans bibliothèque externe avec le client fourni :

```sh
python3 send_osc.py 192.168.1.50 /show/stop
python3 send_osc.py 192.168.1.50 /show/text 'LÉA · MICRO 2'
python3 send_osc.py 192.168.1.50 /show/timer 300
```



## Maintenir l’heure, un compteur ou la mire

Tous ces modes s’éteignent selon `off_time`, **STOP SHOW compris**. Trois possibilités :

1. Mettre `off_time` à **0** pour désactiver le retour au noir, y compris pour STOP SHOW.
2. Choisir un délai adapté dans les réglages (par exemple 3 600 secondes), puis envoyer la consigne.
3. Avec un délai de 15 secondes, envoyer `keepalive` toutes les 5 secondes tant que l’affichage doit rester visible, via une répétition/action périodique configurée dans Companion.

Un `keepalive` prolonge la consigne actuellement visible, quel que soit son type. Arrêter cette répétition quand on souhaite retrouver le délai normal, notamment pour STOP SHOW. Elle ne doit pas tourner à votre insu pendant toute la représentation. Une minuterie ne doit pas être entretenue en répétant sa commande de lancement.

Les commandes concurrentes sont traitées dans leur ordre de réception ; la dernière gagne. STOP SHOW n’a pas de priorité persistante. UDP peut perdre ou réordonner un paquet : préférer HTTP quand l’accusé de réception logiciel est utile.

## Réglages et état HTTP

`GET /api/state`, sans clé, renvoie `cue`, `remaining` (secondes avant le noir, ou `null` lorsque désactivé), `server_time` (temps Unix), `revision` et les paramètres d’affichage. `cue.remaining` est le temps restant du compteur, différent du délai au noir. `GET /api/health` renvoie `ok` et la version.

Sans authentification :

- `GET /api/settings` : configuration.
- `POST /api/settings` : objet partiel, exemple ci-dessous.
- `GET /api/diagnostics` : compteurs OSC reçus/rejetés et dernière information HDMI.
- `GET /api/hdmi` : sorties HDMI actives/inactives et leurs modes, ou 503 si Wayland indisponible.
- `POST /api/hdmi/test` : `{"output":"HDMI-A-1","mode":"1920x1080@60.000000Hz","transform":"180"}` ; recopier le mode exact obtenu par détection.
- `POST /api/hdmi/confirm` : `{}` dans les 20 secondes après un essai réussi.

```json
{"off_time":15,"indicator":true,"font":"sans","size":160,"timezone":"Europe/Zurich","blink_ms":800}
```

Le délai accepté va de 0 à 86 400 secondes. 0 désactive le retour automatique au noir. Taille de 24 à 400. Police `sans`, `serif` ou `mono`. Passer à 0 désactive aussi le délai d’une consigne visible. Repasser de 0 à un délai positif démarre ce délai pour la consigne visible. Entre deux valeurs positives, le nouveau délai vaut pour la prochaine commande ou prolongation. Une consigne déjà éteinte ne réapparaît pas. Aucun appel HTTP GET ne modifie l’état.

## Gestion des mises à jour (v1.3)

La régie web possède les boutons de recherche et d’installation. Pour une intégration : `GET /api/updates` lit l’état local, `POST /api/updates/check` avec `{}` recherche, et `POST /api/updates/install` avec `{}` installe uniquement la proposition déjà trouvée. Aucun autre paramètre n’est accepté. Ne pas mettre l’installation dans une répétition Companion : elle interrompt l’affichage et repart au noir.
