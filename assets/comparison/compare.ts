import ts from "typescript";
import fs from "fs";

function getExportedSymbols(symbol: ts.Symbol): ts.Symbol[] {
  return symbol.exports ? Array.from(symbol.exports.values()) : [];
}

function isSubModule(
  checker: ts.TypeChecker,
  moduleA: ts.Symbol,
  moduleB: ts.Symbol
): {
    isSubModule: boolean;
    subTypeFraction: number;
    subTypes: Record<string, string | null>;
} {
  const exportsA = getExportedSymbols(moduleA);
  const exportsB = getExportedSymbols(moduleB);
  const subs: Record<string, string | null> = {};
  let num_subs = 0;
  for (const symbolB of exportsB) {
    const typeB = symbolB.valueDeclaration ? checker.getTypeOfSymbolAtLocation(symbolB, symbolB.valueDeclaration) : checker.getDeclaredTypeOfSymbol(symbolB);
    subs[symbolB.getName()] = null;
    for (const symbolA of exportsA) {
      const typeA = symbolA.valueDeclaration ? checker.getTypeOfSymbolAtLocation(symbolA, symbolA.valueDeclaration) : checker.getDeclaredTypeOfSymbol(symbolA);
      if (checker.isTypeAssignableTo(typeA, typeB)) {
        subs[symbolB.getName()] = symbolA.getName();
        num_subs++;
        break;
      }
    }
  }
  return {
    isSubModule: num_subs === exportsB.length,
    subTypeFraction: exportsB.length > 0 ? num_subs / exportsB.length : 1,
    subTypes: subs
  }
}

function getRootModuleSymbol(sourceFile: ts.SourceFile, checker: ts.TypeChecker): ts.Symbol | undefined {
  const fileSymbol = checker.getSymbolAtLocation(sourceFile);
  if (fileSymbol) {
    return fileSymbol;
  }
  // for (const stmt of sourceFile.statements) {
  //   if (ts.isModuleDeclaration(stmt) && ts.isStringLiteral(stmt.name)) {
  //     return checker.getSymbolAtLocation(stmt.name);
  //   }
  // }
}

function main() {
    const filePathA = "./predicted.d.ts";
    const filePathB = "./expected.d.ts";
    const program = ts.createProgram([filePathA, filePathB], {});
    const checker = program.getTypeChecker();
    const sourceFileA = program.getSourceFile(filePathA);
    const sourceFileB = program.getSourceFile(filePathB);
    if (!sourceFileA || !sourceFileB) throw Error("Source files not found");
    const sourceSymbolA = getRootModuleSymbol(sourceFileA, checker);
    const sourceSymbolB = getRootModuleSymbol(sourceFileB, checker);
    if (!sourceSymbolA || !sourceSymbolB) throw Error("Symbol not found");
    const resultA = isSubModule(checker, sourceSymbolA, sourceSymbolB);
    const resultB = isSubModule(checker, sourceSymbolB, sourceSymbolA);
    const result = {
      isSound: resultB.isSubModule,
      soundness: resultB.subTypeFraction,
      isComplete: resultA.isSubModule,
      completeness: resultA.subTypeFraction,
      isEquivalent: resultA.isSubModule && resultB.isSubModule,
      equivalence: resultA.subTypeFraction * resultB.subTypeFraction,
      // maps a predicted exported type to an expected exported sub type, if it exists (determines soundness)
      predicted_to_expected_sub: resultB.subTypes,
      // maps an expected exported type to a predicted exported sub type, if it exists (determines completeness)
      expected_to_predicted_sub: resultA.subTypes
    }
    fs.writeFileSync("comparison.json", JSON.stringify(result, null, 2));
}

main();