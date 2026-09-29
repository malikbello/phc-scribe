const TITLES = /^(dr\.?|nurse|mrs\.?|mr\.?|ms\.?|miss|prof\.?|pharm\.?|matron|sister|chief)$/i;

/** "Dr Adé Okafor" -> "Dr Adé"; "Tunde Bakare" -> "Tunde". */
export function displayName(name: string): string {
  const parts = name.trim().split(/\s+/);
  return parts.length > 1 && TITLES.test(parts[0]) ? `${parts[0]} ${parts[1]}` : parts[0];
}
