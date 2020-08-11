<!-- Begin @mdHierarchylevel.md -->

# Type de ressource décrite

## Définition

Cet élément de métadonnées renseigne le type de ressource décrit dans la fiche.
La directive européenne INSPIRE concerne 3 types de ressource :

1. Les `séries de données géographiques` ou `jeu de données géographiques` correspondant à une compilation/ensemble identifiable et cohérent de données géographiques selon un thème dominant. Il peut s’agir d’une couche d’information ou d’un ensemble de couches (base de données géographique).
2. Les `ensembles de séries de données géographiques` correspondant à une compilation de séries de données géographiques partageant la même spécification de produit. Par exemple, la BdOCS2000-CIGAL et la BdOCS2008-CIGAL forment un ensemble de jeux de données géographiques.
3. Les `services de données géographiques`.

Seules les séries et ensembles de séries de données géographiques sont décrites ici. **mdEdit ne permet pas de décrire les services.
Parmi les valeurs possibles de types de ressources définies par la norme ISO 19115 (liste B.# MD_ScopeCode), pour faciliter la saisie dans le cadre du partenariat CIGAL, les valeurs proposées par défaut sont `Jeu / série de données` et `Collection / ensemble de série de données`.

## Recommandations

Dans un souci de simplification et d’homogénéité, il est proposé dans le cadre du partenariat CIGAL de décrire les données à un niveau suffisamment fin (couche d’information ou base de donnée cohérente – ex. : BdOCS2008-CIGAL).
Ainsi, par défaut la valeur utilisée est `jeu de données`.

## Exemples

- Type de donnée décrite : « jeu de données »
- Type de donnée décrite : « ensemble de jeux de données »

<!-- End @mdHierarchylevel.md -->
