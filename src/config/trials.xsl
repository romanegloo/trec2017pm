<xsl:stylesheet version='1.0' xmlns:xsl='http://www.w3.org/1999/XSL/Transform'>
    <xsl:output media-type="text/xml" method="xml" indent="yes"/>
    <xsl:template match="/clinical_study">
    <doc>
        <field name="id"> <xsl:value-of select="id_info/nct_id"/> </field>
        <field name="brief_title"> <xsl:value-of select="brief_title"/> </field>
        <field name="official_title">
            <xsl:value-of select="official_title"/>
        </field>
        <xsl:apply-templates select="brief_summary"/>
        <xsl:apply-templates select="detailed_description"/>
        <field name="overall_status"> <xsl:value-of select="overall_status"/> </field>
        <field name="phase"> <xsl:value-of select="phase"/> </field>
        <field name="study_type"> <xsl:value-of select="study_type"/> </field>
        <xsl:apply-templates select="study_design_info/*"/>
        <field name="condition"> <xsl:value-of select="condition"/> </field>
        <xsl:variable name="intervention">
            <xsl:for-each select="intervention/*">
                <xsl:value-of select="."/>
                <xsl:if test="position()=1"> <xsl:text>:</xsl:text> </xsl:if>
                <xsl:if test="position()!=last()"> <xsl:text> </xsl:text> </xsl:if>
            </xsl:for-each>
        </xsl:variable>
        <field name="intervention"><xsl:value-of select="$intervention"/></field>
        <xsl:apply-templates select="eligibility/criteria"/>
        <field name="eligibility-gender">
            <xsl:value-of select="eligibility/gender"/>
        </field>
        <field name="eligibility-minimum_age">
            <xsl:value-of select="eligibility/minimum_age"/>
        </field>
        <field name="eligibility-maximum_age">
            <xsl:value-of select="eligibility/maximum_age"/>
        </field>
        <xsl:apply-templates select="keyword"/>
        <xsl:apply-templates select="condition_browse"/>
        <xsl:apply-templates select="intervention_browse"/>
    </doc>
    </xsl:template>

    <xsl:template match="brief_summary">
        <xsl:for-each select="textblock">
            <field name="brief_summary"><xsl:value-of select="."/></field>
        </xsl:for-each>
    </xsl:template>

    <xsl:template match="detailed_description">
        <xsl:for-each select="textblock">
            <field name="detailed_description"><xsl:value-of select="."/></field>
        </xsl:for-each>
    </xsl:template>

    <xsl:template match="study_design_info/allocation">
        <field name="study_design_info-allocation"> <xsl:value-of select="."/> </field>
    </xsl:template>
    <xsl:template match="study_design_info/intervention_model">
        <field name="study_design_info-intervention_model"> <xsl:value-of select="."/> </field>
    </xsl:template>
    <xsl:template match="study_design_info/intervention_model_description">
        <field name="study_design_info-primary_purpose"> <xsl:value-of select="."/> </field>
    </xsl:template>
    <xsl:template match="study_design_info/primary_purpose">
        <field name="study_design_info-primary_purpose"> <xsl:value-of select="."/> </field>
    </xsl:template>
    <xsl:template match="study_design_info/observational_model">
        <field name="study_design_info-observational_model"> <xsl:value-of select="."/> </field>
    </xsl:template>
    <xsl:template match="study_design_info/time_perspective">
        <field name="study_design_info-time_perspective"> <xsl:value-of select="."/> </field>
    </xsl:template>
    <xsl:template match="study_design_info/masking">
        <field name="study_design_info-masking"> <xsl:value-of select="."/> </field>
    </xsl:template>
    <xsl:template match="study_design_info/masking_description">
        <field name="study_design_info-masking_description"> <xsl:value-of select="."/> </field>
    </xsl:template>

    <xsl:template match="eligibility/criteria">
        <field name="eligibility-criteria">
            <xsl:for-each select="textblock">
                <xsl:value-of select="."/>
                <xsl:if test="position()!=last()"> <xsl:text> </xsl:text> </xsl:if>
            </xsl:for-each>
        </field>
    </xsl:template>

    <xsl:template match="keyword">
        <xsl:for-each select=".">
            <field name="keyword"><xsl:value-of select="."/></field>
        </xsl:for-each>
    </xsl:template>

    <xsl:template match="condition_browse">
        <xsl:for-each select="mesh_term">
            <field name="condition_browse"><xsl:value-of select="."/></field>
        </xsl:for-each>
    </xsl:template>

    <xsl:template match="intervention_browse">
        <xsl:for-each select="mesh_term">
            <field name="intervention_browse"><xsl:value-of select="."/></field>
        </xsl:for-each>
    </xsl:template>
</xsl:stylesheet>
