<!-- Begin @mdFileIdentifier.md -->

# Identifiant de la fiche

## Définition

Code permettant d’identifier de manière unique la fiche de description de la donnée.
Ce code n’est jamais modifié pour une fiche même lors de sa mise à jour.

S'il n'est pas renseigné, cet identifiant est généré automatiquement par mdEdit sous la forme d'un code unique pseudo aléatoire.

## Recommandations

Afin d’obtenir un code unique, il existe 2 possibilités:

- Construire cet identifiant en associant le code pays de l’organisme propriétaire de la donnée, son numéro SIREN, ainsi qu’un code unique définit par le propriétaire de la donnée (ex.: FR–246300019–143_004).
- Utiliser une URI, c'est à dire une adresse internet (URL) composée du nom de domaine du site internet de l'organisme propriétaire des données suivi d'un identifiant (ex.: http://www.cigalsace.org/FR–246300019–143_004). Cette adresse ne doit pas obligatoirement pointée vers une ressource particulière.

**Structure recommandée de l’identifiant :**

- Code du pays : « FR »
- Séparateur   : « – »
- Code SIREN   : code à 9 chiffres
- Séparateur   : « – »
- Code unique  : choisi par l'administrateur des données

## Exemples

Identifiant de la fiche : « FR–246300019–143_004 »

- FR : code pour la France
- 00019 : numéro SIREN de la Région Alsace
- 120426_004 : numéro unique établi en interne à la Région Alsace, composé de la date de création de la fiche de description (26/04/2012) suivi d’un numéro d’ordre de la fiche.

Identifiant de la fiche : « FR–246300019–110823_BdOCS2008-CIGAL-v2 »

- FR : code pour la France
- 00019 : numéro SIREN de la Région Alsace
- BdOCS2008-CIGAL-v1 : code unique établi en interne à la Région Alsace pour le partenariat CIGAL, composé du nom abrégé officiel de la base de données.

<!-- End @mdFileIdentifier.md -->
